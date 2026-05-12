# ============================================================
# CopilotKit User Identity 与飞书账号绑定
# Phase 1.1
# 核心：identifyUser 返回 {id, name}，其中 id = feishu_open_id
# ============================================================
from typing import Optional


async def resolve_copilotkit_user(context: dict) -> dict:
    """
    CopilotKit User Identity 解析函数

    飞书用户 → CopilotKit User 的映射：
      - CopilotKit user.id   = 飞书 open_id（全局唯一）
      - CopilotKit user.name = 飞书用户姓名

    从请求 header 或 session 中获取飞书用户信息：
      - X-Feishu-User-Id: 飞书 open_id
      - X-Feishu-User-Name: 飞书用户姓名（可选）
    """
    # 实际生产中：从飞书 OAuth 2.0 回调或 JWT token 中解析
    feishu_open_id = context.get("headers", {}).get("x-feishu-user-id")
    feishu_user_name = context.get("headers", {}).get("x-feishu-user-name", "未知用户")

    if not feishu_open_id:
        raise ValueError("缺少飞书用户身份标识（X-Feishu-User-Id header）")

    return {
        "id": feishu_open_id,
        "name": feishu_user_name,
        # 扩展字段（供 Skill 层使用，不写入 CopilotKit 标准接口）
        "metadata": {
            "store_id": context.get("headers", {}).get("x-store-id", "STORE_001"),
            "employee_id": context.get("headers", {}).get("x-employee-id", ""),
            "role": context.get("headers", {}).get("x-employee-role", "clerk"),
        },
    }


# ============================================================
# 飞书 OAuth 2.0 配置（可选）
# 如需完整 OAuth 流程，在此处配置
# ============================================================
FEISHU_OAUTH_CONFIG = {
    "app_id": "{{FEISHU_APP_ID}}",
    "app_secret": "{{FEISHU_APP_SECRET}}",
    "redirect_uri": "{{YOUR_DOMAIN}}/auth/feishu/callback",
    "scope": "im:message:send_as_bot",
}
