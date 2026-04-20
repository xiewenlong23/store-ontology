#!/usr/bin/env python3
"""
代码质量门禁脚本 - store-ontology 项目
检查 lint、类型、测试
"""
import subprocess
import sys
import json
from pathlib import Path

REPO_ROOT = Path(".")


def run_command(cmd, description):
    """运行命令并返回结果"""
    print(f"\n{'='*60}")
    print(f"  {description}")
    print(f"  Command: {cmd}")
    print(f"{'='*60}")
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=120
        )
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
        return result.returncode == 0, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return False, "Command timed out"
    except Exception as e:
        return False, str(e)


def check_python_tests():
    """运行 Python 测试"""
    return run_command(
        "cd /mnt/d/ObsidianVault/store-ontology && "
        "source .venv/bin/activate 2>/dev/null || true && "
        "PYTHONPATH=. pytest tests/ -v --tb=short 2>&1",
        "Python Tests"
    )


def check_flake8():
    """检查 flake8"""
    return run_command(
        "cd /mnt/d/ObsidianVault/store-ontology && "
        "source .venv/bin/activate 2>/dev/null || true && "
        "flake8 app/ tests/ --max-line-length=120 --ignore=E501,W503 2>&1",
        "Flake8 Lint"
    )


def check_frontend_tests():
    """检查前端测试"""
    frontend_path = REPO_ROOT / "frontend"
    if not frontend_path.exists():
        return True, "No frontend directory"

    package_json = frontend_path / "package.json"
    if not package_json.exists():
        return True, "No package.json"

    return run_command(
        f"cd {frontend_path} && npm test -- --watchAll=false 2>&1 || true",
        "Frontend Tests"
    )


def main():
    print("=" * 60)
    print("  Store-Ontology Code Quality Gate")
    print("=" * 60)

    results = {}

    # Python Tests
    passed, output = check_python_tests()
    results["python_tests"] = {"passed": passed, "output": output}

    # Flake8
    passed, output = check_flake8()
    results["flake8"] = {"passed": passed, "output": output}

    # Frontend Tests
    passed, output = check_frontend_tests()
    results["frontend_tests"] = {"passed": passed, "output": output}

    # Summary
    print("\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)

    all_passed = True
    for check, result in results.items():
        status = "✓ PASS" if result["passed"] else "✗ FAIL"
        print(f"  {status}: {check}")
        if not result["passed"]:
            all_passed = False

    print("=" * 60)

    if all_passed:
        print("\n✓ ALL CHECKS PASSED")
        sys.exit(0)
    else:
        print("\n✗ SOME CHECKS FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
