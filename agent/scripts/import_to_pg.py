"""数据迁移脚本：JSON/TTL/YAML → PostgreSQL（WP5，roadmap §1）。

一次性导入现有 workspace 的本体 schema（TTL/YAML）+ 业务数据（JSON）到 PG。
幂等：重复运行只 upsert（不会重复插入）。

用法：
  DATABASE_URL=postgresql://ontology:ontology@localhost:5433/ontology \
    /opt/miniconda3/envs/store-ontology/bin/python agent/scripts/import_to_pg.py

  可选参数：
    --workspace retail       # 只迁移指定 workspace（默认全部）
    --skip-data              # 只迁 schema，不迁数据
    --skip-schema            # 只迁数据，不迁 schema
    --dry-run                # 只打印将要迁移的内容，不写

迁移内容：
  1. TTL（workspace/*/ontology/domains/*/domain.ttl）→ object_types + properties + link_types
  2. Action YAML（domain actions + skills/<process>/actions）→ action_types
  3. JSON 数据（workspace/*/data/*.json）→ entities

迁移后 bootstrap_workspace(ws) 应优先用 PG（WP6 实现）。
"""
import argparse
import json
import os
import sys
from pathlib import Path

# 让 from engine... 可用（agent/ 在 path）
BACKEND = Path(__file__).resolve().parent.parent   # agent/
PROJECT_ROOT = BACKEND.parent                       # 项目根
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(PROJECT_ROOT))   # 让 workspace.*.workspace 可 import


def main():
    parser = argparse.ArgumentParser(description="JSON/TTL/YAML → PG 迁移")
    parser.add_argument("--workspace", help="只迁移指定 workspace（默认全部）")
    parser.add_argument("--skip-data", action="store_true", help="不迁数据")
    parser.add_argument("--skip-schema", action="store_true", help="不迁 schema")
    parser.add_argument("--dry-run", action="store_true", help="只打印不写")
    args = parser.parse_args()

    # 必须 PG 可用
    from engine.db import is_pg_enabled, ping, migrate
    if not is_pg_enabled():
        print("❌ DATABASE_URL 未配置")
        return 1
    if not ping():
        print("❌ PG 不可达（先 docker compose up -d）")
        return 1
    migrate()
    print("✅ migrate OK（schema 就绪）")

    # 加载 workspace 注册表
    from engine.bootstrap import bootstrap
    bootstrap()
    from engine.pack import all_workspace_dirs
    workspaces = all_workspace_dirs()
    if args.workspace:
        workspaces = [ws for ws in workspaces if ws.name == args.workspace]
    if not workspaces:
        print("❌ 无可迁移的 workspace")
        return 1

    stats = {"objects": 0, "properties": 0, "links": 0, "actions": 0, "entities": 0}
    for ws in workspaces:
        print(f"\n=== 迁移 workspace '{ws.name}' ===")
        if not args.skip_schema:
            _migrate_schema(ws, args.dry_run, stats)
        if not args.skip_data:
            _migrate_data(ws, args.dry_run, stats)

    print(f"\n=== 迁移完成 ===")
    print(f"  Object Types: {stats['objects']}")
    print(f"  Properties:   {stats['properties']}")
    print(f"  Link Types:   {stats['links']}")
    print(f"  Action Types: {stats['actions']}")
    print(f"  Entities:     {stats['entities']}")
    return 0


def _migrate_schema(ws, dry_run: bool, stats: dict) -> None:
    """迁 TTL → object_types/link_types + YAML → action_types。"""
    from engine.pack import domains_to_registry
    from engine import pg_ontology_repo as repo

    registry = domains_to_registry(ws, data_dir=ws.data_dir or ".")
    print(f"  schema: {len(registry.object_types)} Object + "
          f"{len(registry.link_types)} Link + "
          f"{len(registry.action_types)} Action")

    if dry_run:
        stats["objects"] += len(registry.object_types)
        stats["links"] += len(registry.link_types)
        stats["actions"] += len(registry.action_types)
        stats["properties"] += sum(len(ot.properties) for ot in registry.object_types.values())
        return

    for ot in registry.object_types.values():
        repo.upsert_object_type(ws.name, ot)
        stats["objects"] += 1
        stats["properties"] += len(ot.properties)
    for lt in registry.link_types.values():
        repo.upsert_link_type(ws.name, lt)
        stats["links"] += 1
    for at in registry.action_types.values():
        repo.upsert_action_type(ws.name, at)
        stats["actions"] += 1


def _migrate_data(ws, dry_run: bool, stats: dict) -> None:
    """迁 workspace/*/data/*.json → entities 表。"""
    data_dir = ws.data_dir
    if not data_dir or not os.path.isdir(data_dir):
        print(f"  data: 无 data_dir（{data_dir}）")
        return

    # 先加载 registry（用于查 storage_file → object_type 映射）
    from engine.pack import domains_to_registry
    registry = domains_to_registry(ws, data_dir=data_dir)
    file_to_objtype = {ot.storage_file: name for name, ot in registry.object_types.items()}

    if dry_run:
        # 统计将迁移的 entity 数
        for fn in os.listdir(data_dir):
            if not fn.endswith(".json"):
                continue
            obj_type = file_to_objtype.get(fn) or _guess_obj_type(fn)
            if not obj_type:
                continue
            path = os.path.join(data_dir, fn)
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    stats["entities"] += len(data)
            except (json.JSONDecodeError, OSError):
                pass
        return

    # 用 PgDataRepository 直接写
    from engine.pg_data_repo import PgDataRepository
    from engine.tenant import TenantContext
    pg_repo = PgDataRepository(workspace_name=ws.name, registry=registry)
    tc_hq = TenantContext(workspace_name=ws.name, org_unit_id="*")

    for fn in sorted(os.listdir(data_dir)):
        if not fn.endswith(".json"):
            continue
        obj_type = file_to_objtype.get(fn) or _guess_obj_type(fn)
        if not obj_type:
            continue
        path = os.path.join(data_dir, fn)
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"    ⚠️ 跳过 {fn}（解析失败: {e}）")
            continue
        if not isinstance(data, list):
            continue
        # users.json 等含 password_hash 的不能脱敏写（要原样）
        for record in data:
            if not isinstance(record, dict) or "id" not in record:
                continue
            # 用 record 自带的 org_unit_id 写（如有）；否则 '*'
            org = record.get("org_unit_id", "*")
            record_tc = TenantContext(workspace_name=ws.name, org_unit_id=org)
            try:
                # edits-only 实体（如 Task/User）用 bypass
                ot = registry.object_types.get(obj_type)
                bypass = bool(ot and getattr(ot, "edits_only_via_actions", False))
                pg_repo.write(obj_type, record_tc, record,
                              create=True, bypass_action_check=bypass)
                stats["entities"] += 1
            except Exception as e:  # noqa: BLE001
                print(f"    ⚠️ 写 {obj_type}/{record.get('id')} 失败: {e}")


def _guess_obj_type(filename: str) -> str:
    """从文件名推导 object_type（当 registry 没 storage_file 映射时）。

    'tasks.json' → 'Task'；'users.json' → 'User'
    """
    name = filename.replace(".json", "").rstrip("s")
    # 处理特殊复数
    if filename == "near_expiry_products.json":
        return "NearExpiryProduct"
    if filename == "permission_grants.json":
        return "PermissionGrant"
    if filename == "org_units.json":
        return "OrgUnit"
    if filename == "categories.json":
        return "Category"
    # 通用：去 s → PascalCase
    parts = name.split("_")
    return "".join(p.capitalize() for p in parts)


if __name__ == "__main__":
    sys.exit(main())
