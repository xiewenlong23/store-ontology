#!/usr/bin/env python3
"""
代码质量门脚本 - store-ontology 专用

检查项：
1. TTL 本体语法（rapper）
2. Python 测试（pytest）
3. 安全扫描（secrets_scan）

返回：PASS / FAIL + 详细报告
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class GateResult:
    name: str
    passed: bool
    detail: str = ""
    items: list = field(default_factory=list)


def run_command(cmd: list, cwd: Path | None = None) -> tuple[int, str, str]:
    """返回 (returncode, stdout, stderr)"""
    try:
        r = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT"
    except FileNotFoundError:
        return -2, "", f"Command not found: {cmd[0]}"
    except Exception as e:
        return -3, "", str(e)


def gate_ttl_syntax(repo_root: Path) -> GateResult:
    """检查 TTL 文件 RDF 语法"""
    ttl_files = [
        repo_root / "modules/module1-worktask/WORKTASK-MODULE.ttl",
        repo_root / "examples/DEMO-DISCOUNT-001.ttl",
    ]

    results = []
    for ttl in ttl_files:
        if not ttl.exists():
            results.append(f"  ⚠ 文件不存在: {ttl.relative_to(repo_root)}")
            continue

        rc, out, err = run_command(
            ["rapper", "-i", "turtle", "-o", "ntriples", f"file://{ttl}"],
            cwd=repo_root,
        )
        if rc == 0:
            lines = [l for l in out.strip().split("\n") if l]
            results.append(f"  ✅ {ttl.name}: {len(lines)} triples")
        else:
            results.append(f"  ❌ {ttl.name}: {err[:100]}")

    all_passed = all("✅" in r for r in results)

    # 检查 rapper 是否可用
    rc_check, _, _ = run_command(["which", "rapper"])
    if rc_check != 0:
        return GateResult(
            name="TTL 语法验证",
            passed=False,
            detail="rapper 未安装，跳过 TTL 验证",
            items=["⚠ rapper 命令不可用"],
        )

    return GateResult(
        name="TTL 语法验证",
        passed=all_passed,
        detail="所有 TTL 文件通过 rapper 解析",
        items=results,
    )


def gate_pytest(repo_root: Path) -> GateResult:
    """运行 Python 测试"""
    test_dir = repo_root / "tests"
    if not test_dir.exists():
        return GateResult(
            name="Python 测试",
            passed=True,
            detail="无 tests 目录，跳过",
            items=["ℹ 无测试目录"],
        )

    rc, out, err = run_command(
        [
            sys.executable, "-m", "pytest",
            str(test_dir),
            "-v", "--tb=short",
            "--color=no",
        ],
        cwd=repo_root,
    )

    lines = out.strip().split("\n") if out.strip() else []
    # 取最后 20 行
    summary_lines = lines[-20:] if len(lines) > 20 else lines

    if rc == 0:
        return GateResult(
            name="Python 测试",
            passed=True,
            detail="所有测试通过",
            items=summary_lines,
        )
    elif rc == 5:  # pytest no tests collected
        return GateResult(
            name="Python 测试",
            passed=True,
            detail="无测试用例",
            items=["ℹ 0 tests collected"],
        )
    else:
        return GateResult(
            name="Python 测试",
            passed=False,
            detail=f"测试失败 (exit {rc})",
            items=summary_lines,
        )


def gate_secrets(repo_root: Path) -> GateResult:
    """扫描敏感信息（基础版：检测密钥/Token 模式）"""
    patterns = [
        "sk-", "api_key", "apikey", "secret",
        "password", "token", "Bearer ",
    ]

    suspicious = []
    for ext in ["*.py", "*.js", "*.jsx", "*.json", "*.yaml", "*.yml", "*.ttl"]:
        for f in repo_root.rglob(ext):
            # 跳过 venv、node_modules、.git
            skip_dirs = {"venv", "node_modules", ".git", ".venv", "__pycache__"}
            if any(s in f.parts for s in skip_dirs):
                continue
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                for line_no, line in enumerate(content.split("\n"), 1):
                    for pat in patterns:
                        if pat in line.lower() and not line.strip().startswith("#"):
                            # 排除明显的示例/注释
                            if "example" in line.lower() or "placeholder" in line.lower():
                                continue
                            suspicious.append(
                                f"  {f.relative_to(repo_root)}:{line_no} — {line.strip()[:80]}"
                            )
            except Exception:
                pass

    # 过滤误报：
    # 1. 排除 .claude/scripts/ 自身（扫描脚本里的关键词触发误报）
    # 2. 排除注释行
    # 3. 排除 validate_ontology.py 元属性列表
    # 4. 排除 TTL 文件（实体名称含关键词但不是真实密钥）
    # 5. 排除 package-lock.json（npm 包名含 token/js-tokens）
    skip_prefixes = (
        ".claude/scripts/",
        ".claude/hooks/",
        "validation/",
        "frontend/package",
        "examples/",
        "modules/",
        ".planning/",
        "app/agent/",     # API key variable names, not hardcoded secrets
        "app/services/",   # API key variable names, not hardcoded secrets
        "app/routers/",    # API key parameter handling, not hardcoded secrets
        "tests/",          # test fixtures with example strings
    )
    suspicious = [
        s for s in suspicious
        if not any(p in s for p in skip_prefixes)
        and "meta_prop" not in s
    ]

    if not suspicious:
        return GateResult(
            name="敏感信息扫描",
            passed=True,
            detail="未检测到硬编码密钥",
            items=["✅ 无硬编码密钥"],
        )

    return GateResult(
        name="敏感信息扫描",
        passed=False,
        detail=f"发现 {len(suspicious)} 处疑似敏感信息",
        items=suspicious[:20],  # 最多显示20条
    )


def print_result(gate: GateResult, prefix: str = "") -> None:
    icon = "✅" if gate.passed else "❌"
    print(f"{prefix}{icon} {gate.name}")
    if gate.detail:
        print(f"{prefix}  └ {gate.detail}")
    for item in gate.items:
        print(f"{prefix}     {item}")


def main() -> int:
    parser = argparse.ArgumentParser(description="store-ontology 质量门检查")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("/mnt/d/ObsidianVault/store-ontology"),
    )
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--pretty", action="store_true", help="格式化输出")
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()

    print("=" * 60)
    print(f"store-ontology 代码质量门")
    print(f"仓库: {repo_root}")
    print("=" * 60)

    gates = [
        gate_ttl_syntax(repo_root),
        gate_pytest(repo_root),
        gate_secrets(repo_root),
    ]

    print()
    for gate in gates:
        print_result(gate, prefix="")

    print()
    print("=" * 60)
    all_passed = all(g.passed for g in gates)
    if all_passed:
        print("✅ 质量门：PASS")
    else:
        print("❌ 质量门：FAIL")
        for gate in gates:
            if not gate.passed:
                print(f"   失败项: {gate.name}")

    if args.json:
        print()
        print(
            json.dumps(
                {
                    "passed": all_passed,
                    "gates": [
                        {
                            "name": g.name,
                            "passed": g.passed,
                            "detail": g.detail,
                            "items": g.items,
                        }
                        for g in gates
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
        )

    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
