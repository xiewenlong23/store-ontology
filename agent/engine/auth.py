"""认证机制（agent 层，纯通用，零身份数据）。

设计文档 §1：agent 层提供认证**机制**（密码 hash/verify、JWT 签发/校验），
不含任何身份数据（User/credentials 存 workspace 的 data/）。

WP1：密码工具（hash_password/verify_password，bcrypt wrap）。
WP2：JWT 签发/校验、AuthContext、token TTL 配置。

实现说明：直接用 bcrypt 库（不用 passlib——passlib 与 bcrypt 5.0 不兼容，
passlib 用 ``bcrypt.__about__.__version__`` 已被 bcrypt 5.0 删除）。
"""
import hashlib
import hmac
import os
import secrets
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

import jwt

try:
    import bcrypt as _bcrypt
    _HAS_BCRYPT = True
except ImportError:  # pragma: no cover - dev 环境兜底
    _HAS_BCRYPT = False


# ============ 密码工具 ============

def hash_password(password: str) -> str:
    """返回 bcrypt 密码哈希（utf-8 文本形式，含 salt 与 version）。

    生产 bcrypt；不可用时回落 sha256+salt 格式 ``sha256$<salt>$<hash>``
    （仅开发兜底，不应在生产使用）。
    """
    pw_bytes = password.encode("utf-8")
    if _HAS_BCRYPT:
        return _bcrypt.hashpw(pw_bytes, _bcrypt.gensalt()).decode("utf-8")
    # 开发兜底
    salt = secrets.token_hex(8)
    h = hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()
    return f"sha256${salt}${h}"


def verify_password(password: str, password_hash: str) -> bool:
    """验证密码与哈希是否匹配。支持 bcrypt 与开发 sha256 兜底格式。"""
    if not password_hash:
        return False
    # 开发兜底格式
    if password_hash.startswith("sha256$"):
        try:
            _, salt, h = password_hash.split("$", 2)
        except ValueError:
            return False
        return hmac.compare_digest(
            hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest(), h)
    # 生产 bcrypt
    if _HAS_BCRYPT:
        try:
            return _bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
        except (ValueError, TypeError):
            return False
    return False


# ============ JWT 签发/校验（WP2）============

# 配置（从 env 读，启动时求值；默认值用于开发兜底）
SECRET_ENV = "JWT_SECRET"
ACCESS_TTL_ENV = "JWT_ACCESS_TTL"      # 默认 7200s=2h
REFRESH_TTL_ENV = "JWT_REFRESH_TTL"    # 默认 604800s=7d


def _get_secret() -> str:
    """读 JWT 签名密钥。未配置 fail-fast（不再静默回落 dev secret）。

    安全理由：静默回落会让生产忘配 env 时，所有 token 可被知道源码的人伪造。
    main.py 启动时也会校验；此处再校验一次，防御直接 import engine.auth 的用法。
    """
    secret = os.getenv(SECRET_ENV)
    if not secret:
        raise RuntimeError(
            f"{SECRET_ENV} 未配置。请在 .env 设置一个随机长字符串"
            f"（生产必填，否则 token 可被伪造）。")
    return secret


def _get_ttl(env_var: str, default: int) -> int:
    raw = os.getenv(env_var)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def get_access_ttl() -> int:
    return _get_ttl(ACCESS_TTL_ENV, 7200)


def get_refresh_ttl() -> int:
    return _get_ttl(REFRESH_TTL_ENV, 604800)


def create_access_token(user_id: str, session_id: str,
                        workspace_names: list) -> str:
    """签发 access token（短 TTL）。

    Claims:
      - sub: user_id
      - sid: session_id（绑定一次登录会话）
      - ws: workspace 白名单（该 user 在这些 ws 认证通过；防跨 ws 越权）
      - typ: "access"
      - iat/exp: 标准 JWT 时间戳
    """
    now = int(time.time())
    payload = {
        "sub": user_id,
        "sid": session_id,
        "ws": workspace_names,
        "typ": "access",
        "iat": now,
        "exp": now + get_access_ttl(),
    }
    return jwt.encode(payload, _get_secret(), algorithm="HS256")


def create_refresh_token(user_id: str, session_id: str) -> str:
    """签发 refresh token（长 TTL）。只携带 sub/sid/typ，不含 ws。"""
    now = int(time.time())
    payload = {
        "sub": user_id,
        "sid": session_id,
        "typ": "refresh",
        "iat": now,
        "exp": now + get_refresh_ttl(),
    }
    return jwt.encode(payload, _get_secret(), algorithm="HS256")


class TokenError(Exception):
    """token 校验失败（无效/过期/类型不符）。"""


def decode_token(token: str, expected_typ: Optional[str] = None) -> dict:
    """校验并解码 JWT。失败抛 TokenError。

    expected_typ: 若指定，token 的 typ claim 必须匹配（防 access/refresh 误用）。
    """
    try:
        payload = jwt.decode(token, _get_secret(), algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise TokenError("token 已过期")
    except jwt.InvalidTokenError as e:
        raise TokenError(f"token 无效: {e}")
    if expected_typ and payload.get("typ") != expected_typ:
        raise TokenError(f"token 类型错误，期望 {expected_typ}")
    return payload


@dataclass(frozen=True)
class AuthContext:
    """请求级身份上下文（auth_middleware 注入，工具/endpoint 经 contextvar 取）。

    设计文档 §1：身份信息由 agent 层认证后注入；workspace 层只读消费。
    WP6 后 actor 一律从 auth_ctx 派生（禁止 LLM 自报）。
    """
    user_id: str
    session_id: str
    workspace_names: tuple = field(default_factory=tuple)   # token 声明的 ws 白名单

    @classmethod
    def anonymous(cls) -> "AuthContext":
        """未认证（WP2 阶段 middleware 不强制，返回 anonymous 而非 401）。"""
        return cls(user_id="", session_id="", workspace_names=())

    def is_authenticated(self) -> bool:
        return bool(self.user_id)

    def can_access_workspace(self, ws_name: str) -> bool:
        """token 声明的 ws 白名单是否含 ws_name（防跨 ws 越权）。"""
        if not self.workspace_names:
            return False
        return ws_name in self.workspace_names


def issue_session_tokens(user_id: str, workspace_names: list) -> dict:
    """登录/刷新成功后签发一对 token（access + refresh）+ session_id。

    返回 ``{access_token, refresh_token, session_id, expires_in}``。
    """
    session_id = str(uuid.uuid4())
    return {
        "access_token": create_access_token(user_id, session_id, workspace_names),
        "refresh_token": create_refresh_token(user_id, session_id),
        "session_id": session_id,
        "expires_in": get_access_ttl(),
    }
