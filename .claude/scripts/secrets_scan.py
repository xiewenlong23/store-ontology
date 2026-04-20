#!/usr/bin/env python3
"""
Secrets 扫描脚本 - 检测硬编码的 secrets、keys、tokens
"""
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(".")


def scan_file(file_path: Path) -> list:
    """扫描单个文件中的 secrets"""
    patterns = [
        (r'ghp_[a-zA-Z0-9]{36}', 'GitHub Personal Access Token'),
        (r'xox[baprs]-[a-zA-Z0-9]{10,}', 'Slack Token'),
        (r'AKIA[0-9A-Z]{16}', 'AWS Access Key'),
        (r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', 'Email (potential)'),
        (r'password\s*=\s*["\']([^"\']{8,})["\']', 'Hardcoded Password'),
        (r'secret\s*=\s*["\']([^"\']{8,})["\']', 'Hardcoded Secret'),
        (r'api[_-]?key\s*=\s*["\']([^"\']{8,})["\']', 'API Key'),
        (r'token\s*=\s*["\']([^"\']{8,})["\']', 'Auth Token'),
    ]

    findings = []
    try:
        content = file_path.read_text(encoding='utf-8', errors='ignore')
        for pattern, description in patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                line_num = content[:match.start()].count('\n') + 1
                findings.append({
                    "file": str(file_path),
                    "line": line_num,
                    "type": description,
                    "match": match.group()[:20] + "..." if len(match.group()) > 20 else match.group()
                })
    except Exception:
        pass
    return findings


def scan_repo():
    """扫描整个仓库"""
    print("=" * 60)
    print("  Secrets Scan")
    print("=" * 60)

    exclude_dirs = {'.git', 'node_modules', '__pycache__', '.venv', 'frontend/node_modules'}
    exclude_exts = {'.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.pdf', '.zip', '.ttf'}

    findings = []
    for path in REPO_ROOT.rglob('*'):
        if path.is_dir():
            if any(ex in path.parts for ex in exclude_dirs):
                continue
        elif path.is_file():
            if path.suffix in exclude_exts:
                continue
            findings.extend(scan_file(path))

    return findings


def main():
    findings = scan_repo()

    if findings:
        print(f"\n✗ Found {len(findings)} potential secrets:")
        for f in findings:
            print(f"  [{f['type']}] {f['file']}:{f['line']} -> {f['match']}")
        print("\n⚠️  Please review and remediate before committing")
        exit(1)
    else:
        print("\n✓ No secrets detected")
        exit(0)


if __name__ == "__main__":
    main()
