#!/usr/bin/env python3
# ============================================================
# ABOX + TBOX 数据导入脚本 — Phase 3.4
# 将 TTL 本体 + 测试数据导入 GraphDB
# 用法: python scripts/load_abox.py [--repo REPO_NAME]
#
# 导入顺序：
#   1. TBOX（本体模块）→ 先导入，建立 schema
#   2. ABOX（测试数据）→ 后导入，包含实例
# ============================================================
import argparse
import httpx
import sys
from pathlib import Path

GRAPHDB_BASE = "http://localhost:7200"
DEFAULT_REPO = "store-ontology"

# TBOX 模块文件（本体 schema）
TBOX_FILES = [
    "ontology/tbox/modules/00-enums/ENUMS-MODULE.ttl",
    "ontology/tbox/modules/01-product/PRODUCT-MODULE.ttl",
    "ontology/tbox/modules/02-discount/DISCOUNT-MODULE.ttl",
    "ontology/tbox/modules/03-task/TASK-MODULE.ttl",
    "ontology/tbox/modules/04-employee/EMPLOYEE-MODULE.ttl",
    "ontology/tbox/store-ontology.ttl",          # 主本体（合并导入）
]

# ABOX 实例数据
ABOX_FILE = "ontology/abox/test-data.ttl"


def create_repository(base_url: str, repo_name: str) -> bool:
    """创建 GraphDB Repository"""
    config = {
        "id": repo_name,
        "title": "Store Ontology Repository",
        "type": "master",
        "context": "urn:x-arq:default-graph",
        "param": {
            "baseURL": f"http://{repo_name}/",
            "defaultSyntax": "TTL",
            "verifyBNodes": "true",
            "checkInstances": "true",
            "disableSameAs": "false",
            "rdfs": "true",
            "rdfsSubClassReasoning": "true",
            "storage": {"type": "persistent"},
        },
    }

    print(f"[1/4] 创建 Repository: {repo_name}")
    try:
        resp = httpx.post(
            f"{base_url}/rest/repositories",
            json=config,
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        if resp.status_code in (201, 409):
            print(f"  ✅ Repository 就绪 ({resp.status_code})")
        else:
            print(f"  ❌ 创建失败: {resp.status_code} {resp.text[:200]}")
            return False
    except httpx.ConnectError:
        print(f"  ❌ 无法连接 GraphDB ({base_url})")
        print(f"     请先运行: docker-compose up -d graphdb")
        return False

    return True


def wait_for_repo(base_url: str, repo_name: str) -> bool:
    """等待 Repository 就绪"""
    print(f"[2/4] 等待 Repository 就绪...")
    import time
    for attempt in range(10):
        try:
            resp = httpx.get(f"{base_url}/rest/repositories/{repo_name}/size", timeout=5)
            if resp.status_code == 200:
                print(f"  ✅ Repository 就绪")
                return True
        except httpx.HTTPError:
            pass
        time.sleep(1)
    print(f"  ⚠️  Repository 未就绪，继续尝试导入...")
    return True


def upload_ttl(base_url: str, repo_name: str, ttl_path: Path, label: str) -> bool:
    """上传单个 TTL 文件到 GraphDB"""
    if not ttl_path.exists():
        print(f"  ❌ 文件不存在: {ttl_path}")
        return False

    with open(ttl_path, "rb") as f:
        ttl_content = f.read()

    upload_url = f"{base_url}/rest/data/import/upload/{repo_name}"
    try:
        resp = httpx.post(
            upload_url,
            files={"file": (str(ttl_path), ttl_content, "application/x-turtle")},
            data={"context": "urn:x-arq:default-graph", "replaceGraphs": "true"},
            timeout=60,
        )
        if resp.status_code in (200, 204, 201):
            print(f"  ✅ {label}: {ttl_path.name}")
            return True
        else:
            print(f"  ⚠️  {label}: {resp.status_code} {resp.text[:100]}")
            return False
    except httpx.HTTPError as e:
        print(f"  ❌ {label} 上传失败: {e}")
        return False


def verify_import(base_url: str, repo_name: str) -> bool:
    """验证导入结果"""
    print("\n[4/4] 验证导入结果...")
    queries = [
        ("门店", 'SELECT (COUNT(*) AS ?c) WHERE { ?s a <http://store-ontology.org/ontology/Store> }'),
        ("商品", 'SELECT (COUNT(*) AS ?c) WHERE { ?s a <http://store-ontology.org/ontology/Product> }'),
        ("员工", 'SELECT (COUNT(*) AS ?c) WHERE { ?s a <http://store-ontology.org/ontology/Employee> }'),
        ("临期商品(≤14天)", """
            PREFIX store: <http://store-ontology.org/ontology/>
            SELECT (COUNT(*) AS ?c) WHERE {
                ?p a store:Product .
                ?p store:shelfDate ?sd .
                FILTER(?sd <= 14)
            }
        """),
    ]

    all_ok = True
    for label, query in queries:
        try:
            resp = httpx.get(
                f"{base_url}/repositories/{repo_name}",
                params={"query": query.strip()},
                headers={"Accept": "application/sparql-results+json"},
                timeout=15,
            )
            if resp.status_code == 200:
                bindings = resp.json().get("results", {}).get("bindings", [])
                count = bindings[0].get("c", {}).get("value", "N/A") if bindings else "0"
                print(f"  ✅ {label}: {count}")
            else:
                print(f"  ⚠️  {label}: {resp.status_code}")
                all_ok = False
        except Exception as e:
            print(f"  ⚠️  {label}: {e}")
            all_ok = False

    return all_ok


def main():
    parser = argparse.ArgumentParser(description="导入 TBOX + ABOX 到 GraphDB")
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--graphdb", default=GRAPHDB_BASE)
    args = parser.parse_args()

    script_dir = Path(__file__).parent.resolve()
    project_root = script_dir.parent

    print(f"GraphDB: {args.graphdb}")
    print(f"Repository: {args.repo}")

    # 1. 创建 Repository
    if not create_repository(args.graphdb, args.repo):
        sys.exit(1)

    # 2. 等待就绪
    wait_for_repo(args.graphdb, args.repo)

    # 3. 上传 TBOX（先 schema）
    print("[3/4] 导入 TBOX 本体...")
    tbox_ok = True
    for rel_path in TBOX_FILES:
        ttl_path = project_root / rel_path
        ok = upload_ttl(args.graphdb, args.repo, ttl_path, "TBOX")
        if not ok:
            tbox_ok = False

    # 上传 ABOX（后数据）
    print("\n    导入 ABOX 数据...")
    abox_path = project_root / ABOX_FILE
    upload_ttl(args.graphdb, args.repo, abox_path, "ABOX")

    # 4. 验证
    verify_import(args.graphdb, args.repo)


if __name__ == "__main__":
    main()
