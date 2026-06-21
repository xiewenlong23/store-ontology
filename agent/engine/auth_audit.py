"""agent 层认证审计（设计文档 §5 WP2）。

记录 login/logout/token_fail/refresh 等认证事件，独立于 workspace 层的
tool/action 审计（后者由 WP5 PermissionEvaluator 写入 workspace/data/audit_logs.json）。

存储：agent/data/auth_audit.json（append-only JSONL-like 数组）。
设计原则：审计失败本身不应导致请求失败（写入用 try/except 兜底）。
"""
import json
import os
import threading
from datetime import datetime
from typing import Optional

_AUDIT_LOCK = threading.Lock()


def _audit_path() -> str:
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # agent/
    data_dir = os.path.join(base, "data")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "auth_audit.json")


def log_auth_event(event_type: str, *,
                   username: Optional[str] = None,
                   user_id: Optional[str] = None,
                   workspace_name: Optional[str] = None,
                   outcome: str = "success",
                   detail: str = "",
                   client_ip: Optional[str] = None) -> None:
    """记录一条认证审计事件。

    event_type: login / logout / token_fail / refresh / token_invalid
    outcome: success / failed
    """
    entry = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "event": event_type,
        "username": username,
        "user_id": user_id,
        "workspace_name": workspace_name,
        "outcome": outcome,
        "detail": detail,
        "client_ip": client_ip,
    }
    try:
        with _AUDIT_LOCK:
            path = _audit_path()
            existing = []
            if os.path.exists(path):
                try:
                    with open(path, encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            existing = data
                except (json.JSONDecodeError, OSError):
                    existing = []
            existing.append(entry)
            # 滚动截断（保留最近 1000 条，避免无限增长）
            if len(existing) > 1000:
                existing = existing[-1000:]
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(existing, f, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
    except Exception as e:  # noqa: BLE001 - 审计失败不应阻断请求
        print(f"[auth_audit] 写入失败（不影响请求）: {e}")
