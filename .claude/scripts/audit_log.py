#!/usr/bin/env python3
"""
审计日志脚本 - store-ontology 项目
用法: python3 .claude/scripts/audit_log.py --step <步骤> --command "<命令>" --goal "<目标>" --status <done|blocked|done_with_concerns>
"""
import argparse
import json
import os
from datetime import datetime
from pathlib import Path

AUDIT_DIR = Path(".planning/audit/runs")
PM_DIR = Path(".planning/pm/current")


def ensure_dirs():
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    PM_DIR.mkdir(parents=True, exist_ok=True)


def get_run_id():
    """获取或生成 run_id"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"run_{timestamp}"


def write_audit_log(run_id: str, step: str, command: str, goal: str, status: str, artifact: str = None):
    """写审计日志"""
    ensure_dirs()
    log_file = AUDIT_DIR / run_id / f"{step}.md"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    content = f"""# Audit Log: {step}

## Metadata

| Field | Value |
|-------|-------|
| Run ID | {run_id} |
| Step | {step} |
| Command | {command} |
| Goal | {goal} |
| Status | {status} |
| Timestamp | {datetime.now().isoformat()} |

## Artifact

{artifact or 'N/A'}

## Notes

<!-- 补充说明 -->

"""
    log_file.write_text(content)
    print(f"✓ Audit log written: {log_file}")


def write_summary(run_id: str, phases: dict):
    """写汇总报告"""
    ensure_dirs()
    summary_file = AUDIT_DIR / run_id / "SUMMARY.md"

    lines = [f"# Audit Summary: {run_id}\n", "## Phases\n", "| Phase | Status |", "|-------|--------|"]
    for phase, status in phases.items():
        lines.append(f"| {phase} | {status} |")

    summary_file.write_text("\n".join(lines))
    print(f"✓ Summary written: {summary_file}")


def main():
    parser = argparse.ArgumentParser(description="Audit log writer for store-ontology")
    parser.add_argument("--step", required=True, help="Step name (e.g., fad-pipeline-start)")
    parser.add_argument("--command", required=True, help="Command executed")
    parser.add_argument("--goal", required=True, help="Goal/objective")
    parser.add_argument("--status", required=True, choices=["done", "blocked", "done_with_concerns"])
    parser.add_argument("--run-id", help="Run ID (auto-generated if not provided)")
    parser.add_argument("--artifact", help="Artifact path or content")
    parser.add_argument("--pretty", action="store_true", help="Pretty print output")

    args = parser.parse_args()
    run_id = args.run_id or get_run_id()

    write_audit_log(
        run_id=run_id,
        step=args.step,
        command=args.command,
        goal=args.goal,
        status=args.status,
        artifact=args.artifact
    )

    if args.pretty:
        print(f"\nRun ID: {run_id}")


if __name__ == "__main__":
    main()
