"""OntoAgent CLI —— 客户 onboarding 命令行入口（P3）。

用法：
  python cli.py copy <pack> <customer_id> [--name 客户名]
      Copy 行业包到客户目录（步骤①）

  python cli.py seed <customer_id> <source_file> <object_type>
      灌入数据（步骤③），按本体校验

  python cli.py start <customer_id>
      启动客户 agent 实例（步骤⑤），验证 onboarding 完成
"""
import argparse
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ontology.onboarding import copy_pack_to_customer, seed_customer_data
from ontology.customer import CustomerConfig, register_customer
from ontology.customer_bootstrap import (bootstrap_customer,
                                          _build_registry_from_customer_ontology,
                                          reset_instances)


def cmd_copy(args):
    """步骤①：copy 行业包到客户目录。"""
    base = os.path.dirname(os.path.abspath(__file__))
    pack_root = os.path.join(base, "packs", args.pack)
    if not os.path.isdir(pack_root):
        print(f"错误：行业包 '{args.pack}' 不存在（{pack_root}）")
        sys.exit(1)

    customer_root = os.path.join(base, "..", "data", "customers", args.customer_id)
    copy_pack_to_customer(
        pack_root=pack_root, customer_root=customer_root,
        customer_id=args.customer_id,
        customer_name=args.name or args.customer_id,
        pack_name=args.pack)
    print(f"✓ 已 copy 行业包 '{args.pack}' 到 {customer_root}")
    print(f"  ontology/: {customer_root}/ontology/")
    print(f"  config:    {customer_root}/config.yaml")
    print(f"  下一步：编辑 ontology/ 调整本体（步骤②），然后 cli.py seed 灌数据（步骤③）")


def cmd_seed(args):
    """步骤③：灌入数据。"""
    base = os.path.dirname(os.path.abspath(__file__))
    customer_root = os.path.join(base, "..", "data", "customers", args.customer_id)
    ontology_dir = os.path.join(customer_root, "ontology")
    data_dir = os.path.join(customer_root, "data")

    if not os.path.isdir(ontology_dir):
        print(f"错误：客户 '{args.customer_id}' 无 ontology 目录（先运行 copy）")
        sys.exit(1)

    reg = _build_registry_from_customer_ontology(ontology_dir, data_dir)
    out = seed_customer_data(
        customer_data_dir=data_dir,
        source_file=args.source_file,
        object_type=args.object_type,
        registry=reg,
        customer_id=args.customer_id)
    print(f"✓ 已灌入 {args.object_type} 数据到 {out}")
    print(f"  下一步：编辑 config.yaml 配存储（步骤④），然后 cli.py start（步骤⑤）")


def cmd_start(args):
    """步骤⑤：启动客户 agent 实例（验证 onboarding）。"""
    base = os.path.dirname(os.path.abspath(__file__))
    customer_root = os.path.join(base, "..", "data", "customers", args.customer_id)
    data_dir = os.path.join(customer_root, "data")

    from ontology.customer import load_customer_config
    cfg = load_customer_config(customer_root)
    register_customer(cfg)
    # I-2: 失效缓存，确保读取最新本体（客户可能刚编辑过 ontology/）
    from ontology.customer_bootstrap import invalidate_customer
    invalidate_customer(args.customer_id)

    inst = bootstrap_customer(args.customer_id)
    print(f"✓ 客户 '{args.customer_id}' agent 实例已启动")
    print(f"  Objects: {sorted(inst.registry.object_types.keys())}")
    print(f"  Actions: {len(inst.registry.action_types)} 个")
    print(f"  数据目录: {inst.repository.data_dir}")
    print(f"  onboarding 完成！可通过对话/自动化/看板使用。")


def main():
    parser = argparse.ArgumentParser(description="OntoAgent 客户 onboarding CLI")
    sub = parser.add_subparsers(dest="command")

    p_copy = sub.add_parser("copy", help="Copy 行业包到客户目录")
    p_copy.add_argument("pack", help="行业包名（如 retail）")
    p_copy.add_argument("customer_id", help="客户 ID")
    p_copy.add_argument("--name", help="客户显示名")

    p_seed = sub.add_parser("seed", help="灌入数据")
    p_seed.add_argument("customer_id")
    p_seed.add_argument("source_file", help="JSON 数据文件")
    p_seed.add_argument("object_type", help="Object Type 名（如 Product）")

    p_start = sub.add_parser("start", help="启动客户 agent 实例")
    p_start.add_argument("customer_id")

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
