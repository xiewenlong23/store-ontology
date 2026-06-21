"""OntologyAgent CLI —— workspace onboarding 命令行入口（架构 spec §3.3 onboarding）。

用法：
  python cli.py copy <pack> <workspace_name> [--name 显示名]
      Copy 行业包到 workspace 目录（步骤①）

  python cli.py seed <workspace_name> <source_file> <object_type>
      灌入数据（步骤③），按本体校验

  python cli.py start <workspace_name>
      启动 workspace 的 agent 实例（步骤⑤），验证 onboarding 完成
"""
import argparse
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.onboarding import copy_pack_to_workspace, seed_workspace_data
from engine.workspace import WorkspaceConfig, register_workspace
from engine.workspace_bootstrap import (bootstrap_workspace,
                                          _build_registry_from_workspace_ontology,
                                          reset_instances)


def cmd_copy(args):
    """步骤①：copy 行业包到 workspace 目录。"""
    base = os.path.dirname(os.path.abspath(__file__))
    pack_root = os.path.join(base, "..", "workspace", args.pack)
    if not os.path.isdir(pack_root):
        print(f"错误：行业包 '{args.pack}' 不存在（{pack_root}）")
        sys.exit(1)

    workspace_root = os.path.join(base, "..", "workspace", args.workspace_name)
    copy_pack_to_workspace(
        pack_root=pack_root, workspace_root=workspace_root,
        workspace_name=args.workspace_name,
        workspace_label=args.name or args.workspace_name,
        pack_name=args.pack)
    print(f"✓ 已 copy 行业包 '{args.pack}' 到 {workspace_root}")
    print(f"  ontology/: {workspace_root}/ontology/")
    print(f"  config:    {workspace_root}/config.yaml")
    print(f"  下一步：编辑 ontology/ 调整本体（步骤②），然后 cli.py seed 灌数据（步骤③）")


def cmd_seed(args):
    """步骤③：灌入数据。"""
    base = os.path.dirname(os.path.abspath(__file__))
    workspace_root = os.path.join(base, "..", "workspace", args.workspace_name)
    ontology_dir = os.path.join(workspace_root, "ontology")
    data_dir = os.path.join(workspace_root, "data")

    if not os.path.isdir(ontology_dir):
        print(f"错误：workspace '{args.workspace_name}' 无 ontology 目录（先运行 copy）")
        sys.exit(1)

    reg = _build_registry_from_workspace_ontology(ontology_dir, data_dir)
    out = seed_workspace_data(
        workspace_data_dir=data_dir,
        source_file=args.source_file,
        object_type=args.object_type,
        registry=reg,
        workspace_name=args.workspace_name)
    print(f"✓ 已灌入 {args.object_type} 数据到 {out}")
    print(f"  下一步：编辑 config.yaml 配存储（步骤④），然后 cli.py start（步骤⑤）")


def cmd_start(args):
    """步骤⑤：启动 workspace 的 agent 实例（验证 onboarding）。"""
    base = os.path.dirname(os.path.abspath(__file__))
    workspace_root = os.path.join(base, "..", "workspace", args.workspace_name)
    data_dir = os.path.join(workspace_root, "data")

    from engine.workspace import load_workspace_config
    cfg = load_workspace_config(workspace_root)
    register_workspace(cfg)
    # I-2: 失效缓存，确保读取最新本体（workspace 可能刚编辑过 ontology/）
    from engine.workspace_bootstrap import invalidate_workspace
    invalidate_workspace(args.workspace_name)

    inst = bootstrap_workspace(args.workspace_name)
    print(f"✓ workspace '{args.workspace_name}' agent 实例已启动")
    print(f"  Objects: {sorted(inst.registry.object_types.keys())}")
    print(f"  Actions: {len(inst.registry.action_types)} 个")
    print(f"  数据目录: {inst.repository.data_dir}")
    print(f"  onboarding 完成！可通过对话/自动化/看板使用。")


def main():
    parser = argparse.ArgumentParser(description="OntologyAgent workspace onboarding CLI")
    sub = parser.add_subparsers(dest="command")

    p_copy = sub.add_parser("copy", help="Copy 行业包到 workspace 目录")
    p_copy.add_argument("pack", help="行业包名（如 retail）")
    p_copy.add_argument("workspace_name", help="workspace 名称")
    p_copy.add_argument("--name", help="workspace 显示名")

    p_seed = sub.add_parser("seed", help="灌入数据")
    p_seed.add_argument("workspace_name")
    p_seed.add_argument("source_file", help="JSON 数据文件")
    p_seed.add_argument("object_type", help="Object Type 名（如 Product）")

    p_start = sub.add_parser("start", help="启动 workspace 的 agent 实例")
    p_start.add_argument("workspace_name")

    args = parser.parse_args()
    if args.command == "copy":
        cmd_copy(args)
    elif args.command == "seed":
        cmd_seed(args)
    elif args.command == "start":
        cmd_start(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
