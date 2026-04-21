#!/usr/bin/env python3
"""
审计日志脚本 - 为 FAD 工作流创建 Markdown 审计记录。
"""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

STATUSES = {"done", "done_with_concerns", "blocked", "needs_context"}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def run_id_now() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = uuid4().hex[:6]
    return f"{stamp}-{suffix}"


def timestamp_for_filename() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def slugify(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip().lower())
    return normalized.strip("-") or "step"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="写一条 Markdown 审计步骤日志。")
    parser.add_argument("--repo-root", default=".", help="仓库根目录。")
    parser.add_argument("--run-id", default="", help="已有 run ID，省略则自动生成。")
    parser.add_argument("--step", required=True, help="步骤标识符（用于文件名和元数据）。")
    parser.add_argument(
        "--status",
        default="done",
        choices=sorted(STATUSES),
        help="步骤状态。",
    )
    parser.add_argument("--command", default="", help="命令/工作流名称。")
    parser.add_argument("--actor", default="agent", help="执行者标签。")
    parser.add_argument("--goal", default="", help="需求或目标摘要。")
    parser.add_argument("--artifact", default="", help="产物路径。")
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="格式化输出（供人类阅读）。",
    )
    return parser.parse_args()


def build_audit_content(
    step: str,
    status: str,
    command: str,
    actor: str,
    goal: str,
    artifact: str,
    run_id: str,
    now: str,
) -> str:
    status_emoji = {
        "done": "✅",
        "done_with_concerns": "⚠️",
        "blocked": "🚫",
        "needs_context": "❓",
    }.get(status, "❓")

    lines = [
        f"# {status_emoji} Step: {step}",
        "",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| Step | {step} |",
        f"| Status | {status} |",
        f"| Command | {command} |",
        f"| Actor | {actor} |",
        f"| Run ID | {run_id} |",
        f"| Timestamp | {now} |",
    ]
    if goal:
        lines.append(f"| Goal | {goal} |")
    if artifact:
        lines.append(f"| Artifact | {artifact} |")

    return "\n".join(lines)


def main() -> int:
    args = parse_args()

    repo_root = Path(args.repo_root).resolve()
    now = now_iso()

    if args.run_id:
        run_id = args.run_id
    else:
        run_id = run_id_now()

    audit_dir = repo_root / ".planning" / "audit" / "runs" / run_id
    audit_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{timestamp_for_filename()}-{slugify(args.step)}.md"
    filepath = audit_dir / filename

    content = build_audit_content(
        step=args.step,
        status=args.status,
        command=args.command,
        actor=args.actor,
        goal=args.goal,
        artifact=args.artifact,
        run_id=run_id,
        now=now,
    )

    filepath.write_text(content + "\n", encoding="utf-8")

    # 同时追加到汇总 index.md
    index_path = audit_dir / "INDEX.md"
    index_line = f"| {now} | `{args.step}` | {args.status} | {args.command} | {args.goal or ''} |\n"
    if index_path.exists():
        existing = index_path.read_text(encoding="utf-8")
        # 去掉末尾换行，追加新行
        if existing.rstrip("\n").endswith("|"):
            index_content = existing + index_line
        else:
            index_content = existing.rstrip("\n") + "\n" + index_line
    else:
        index_content = (
            "| Timestamp | Step | Status | Command | Goal |\n"
            "|---|---|---|---|---|\n"
            + index_line
        )
    index_path.write_text(index_content, encoding="utf-8")

    if args.pretty:
        print(f"[audit] {filepath.relative_to(repo_root)}")
        print(f"  run_id : {run_id}")
        print(f"  step   : {args.step}")
        print(f"  status : {args.status}")

    print(run_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
