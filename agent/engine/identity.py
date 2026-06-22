"""workspace 身份数据访问（agent 层机制 + workspace 层数据）。

设计文档 §1 边界：
- **agent 层（本文件 + auth.py）**：提供机制——读 workspace 的 users.json 验密码、
  生成初始 admin、找 Employee 关联。**不含任何硬编码的身份数据**。
- **workspace 层**： owns users.json/roles.json/permission_grants.json 数据 +
  identity domain TTL 本体（User/Role/PermissionGrant）。

WP1 提供的能力：
- ``verify_credentials(workspace_name, username, password)`` —— 登录验证
- ``get_employee_by_user(workspace_name, user_id)`` —— User→Employee 反查（WP4 后生效）
- ``seed_workspace_identity(workspace_name)`` —— 首次启动种入 admin（幂等）
- ``list_user_workspaces(username, password)`` —— 跨 workspace 扫描，登录用
"""
import json
import os
from datetime import datetime
from typing import Dict, List, Optional

from engine.auth import hash_password, verify_password


def _workspace_data_dir(workspace_name: str) -> Optional[str]:
    """取 workspace 的 data_dir（从 pack 注册表）。未注册返回 None。"""
    from engine.pack import get_workspace_dir
    ws = get_workspace_dir(workspace_name)
    if not ws or not ws.data_dir:
        return None
    return ws.data_dir


def _load_users(data_dir: str) -> List[dict]:
    """直接从 data_dir 读 users.json（不经 Repository，避免循环依赖）。"""
    path = os.path.join(data_dir, "users.json")
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_users(data_dir: str, users: List[dict]) -> None:
    """直接写 users.json（首次初始化用；正常运行走 Repository/Action）。"""
    os.makedirs(data_dir, exist_ok=True)
    path = os.path.join(data_dir, "users.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


def verify_credentials(workspace_name: str, username: str, password: str) -> Optional[dict]:
    """在指定 workspace 验证用户名+密码。

    成功返回 user dict（**剥离 password_hash**），失败返回 None。
    workspace 未注册/无 users.json/用户禁用/密码错均返回 None。
    """
    data_dir = _workspace_data_dir(workspace_name)
    if not data_dir:
        return None
    for u in _load_users(data_dir):
        if u.get("username") != username:
            continue
        if u.get("status") != "active":
            return None
        if verify_password(password, u.get("password_hash", "")):
            return {k: v for k, v in u.items() if k != "password_hash"}
        return None
    return None


def get_employee_by_user(workspace_name: str, user_id: str) -> Optional[dict]:
    """在该 workspace 找 user_id 对应的 Employee 记录。

    Employee.user_id 反向引用字段由 WP4 加入 personnel domain；
    WP1 阶段 Employee 尚无 user_id 字段，本函数返回 None（前向兼容）。
    """
    data_dir = _workspace_data_dir(workspace_name)
    if not data_dir:
        return None
    emp_path = os.path.join(data_dir, "employees.json")
    if not os.path.exists(emp_path):
        return None
    try:
        with open(emp_path, encoding="utf-8") as f:
            employees = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
    for e in employees:
        if e.get("user_id") == user_id:
            return e
    return None


def list_user_workspaces(username: str, password: str) -> List[Dict]:
    """扫描所有 workspace，返回该用户认成功的 workspace 列表（登录用）。

    返回 memberships：``[{workspace_name, user_id, role, org_unit_id, display_name}]``。
    role/org_unit_id 从该 workspace 的 Employee（user_id 反向引用）查得；
    Employee 缺失时（如 admin 系统账号）role=system_admin / org_unit_id=*。
    """
    from engine.pack import all_workspace_dirs
    memberships = []
    for ws in all_workspace_dirs():
        user = verify_credentials(ws.name, username, password)
        if user:
            # 查 Employee 关联（user_id 反向引用）推导 role/org_unit
            emp = get_employee_by_user(ws.name, user.get("id"))
            if emp:
                role = emp.get("role") or "system_admin"
                org_unit = emp.get("org_unit_id") or emp.get("store_id") or "*"
            else:
                # admin 等系统账号无 Employee → 默认 system_admin + 总部视角
                role = "system_admin"
                org_unit = "*"
            memberships.append({
                "workspace_name": ws.name,
                "workspace_display_name": ws.display_name,
                "user_id": user.get("id"),
                "username": user.get("username"),
                "display_name": user.get("display_name"),
                "role": role,
                "org_unit_id": org_unit,
            })
    return memberships


# ============ 首次初始化引导（设计文档 §5 WP1）============

_DEFAULT_ADMIN_USERNAME = "admin"
_DEFAULT_ADMIN_PASSWORD_ENV = "INITIAL_ADMIN_PASSWORD"
_DEFAULT_ADMIN_PASSWORD = "admin123"   # 仅首次初始化默认；生产应通过 env 覆盖


def seed_workspace_identity(workspace_name: str) -> bool:
    """首次初始化：若 users.json 为空，种入一个 system_admin 用户。幂等。

    - 默认用户名 ``admin``，密码从 ``INITIAL_ADMIN_PASSWORD`` env 读，回落 ``admin123``。
    - 已有用户则不操作（返回 False）。
    - 种入成功返回 True。

    设计文档 §2.3：system_admin 是 workspace 自管的超级角色；本函数只创建 User
    记录，system_admin 的 PermissionGrant（全 allow 或 eval bypass）由 WP5
    PermissionEvaluator 处理（actor.role == "system_admin" 短路）。
    """
    data_dir = _workspace_data_dir(workspace_name)
    if not data_dir:
        return False
    existing = _load_users(data_dir)
    if existing:
        return False
    password = os.getenv(_DEFAULT_ADMIN_PASSWORD_ENV) or _DEFAULT_ADMIN_PASSWORD
    admin = {
        "id": "user_admin",
        "username": _DEFAULT_ADMIN_USERNAME,
        "password_hash": hash_password(password),
        "display_name": "系统管理员",
        "status": "active",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "workspace_name": workspace_name,
        "org_unit_id": "*",   # 总部视角
    }
    _save_users(data_dir, [admin])
    return True


def seed_all_workspaces() -> None:
    """遍历所有已注册 workspace，种入初始 admin（幂等，bootstrap 调用）。"""
    from engine.pack import all_workspace_dirs
    for ws in all_workspace_dirs():
        try:
            if seed_workspace_identity(ws.name):
                print(f"[identity] workspace '{ws.name}': 已种入初始 admin "
                      f"(用户名=admin，密码见 INITIAL_ADMIN_PASSWORD env 或默认 admin123)")
        except Exception as e:  # noqa: BLE001
            print(f"[identity] workspace '{ws.name}' 种子初始化失败: {e}")
