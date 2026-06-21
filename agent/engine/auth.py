"""认证机制（agent 层，纯通用，零身份数据）。

设计文档 §1：agent 层提供认证**机制**（密码 hash/verify、JWT 签发/校验），
不含任何身份数据（User/credentials 存 workspace 的 data/）。

WP1：只放密码工具（hash_password/verify_password，bcrypt wrap）。
WP2：加 JWT 签发/校验、AuthContext、auth_middleware。

实现说明：直接用 bcrypt 库（不用 passlib——passlib 与 bcrypt 5.0 不兼容，
passlib 用 ``bcrypt.__about__.__version__`` 已被 bcrypt 5.0 删除）。
"""
import hashlib
import hmac
import secrets

try:
    import bcrypt as _bcrypt
    _HAS_BCRYPT = True
except ImportError:  # pragma: no cover - dev 环境兜底
    _HAS_BCRYPT = False


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
