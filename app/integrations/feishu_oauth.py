# ============================================================
# 飞书 OAuth 2.0 回调路由
# Phase 1.1
# 路由：GET /auth/feishu/callback
# ============================================================
import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from app.config import settings

router = APIRouter(prefix="/auth/feishu", tags=["认证"])


@router.get("/callback")
async def feishu_oauth_callback(
    code: str = Query(..., description="飞书授权码"),
    state: str = Query(default="", description="CSRF state 参数"),
):
    """
    飞书 OAuth 2.0 授权码回调

    流程：
    1. 用户在飞书授权页同意授权
    2. 飞书回调此端点，带上 code（授权码）
    3. 用 code 换 user_access_token
    4. 用 user_access_token 换取用户基本信息（open_id / name）
    5. 生成 session，重定向到前端

    前端拼接 header：
      X-Feishu-User-Id: {open_id}
      X-Feishu-User-Name: {name}
      X-Store-Id: {store_id}（可从员工数据中查）
    """
    if not code:
        raise HTTPException(status_code=400, detail="缺少授权码")

    # Step 1：用 code 换 user_access_token
    token_url = "https://open.feishu.cn/open-apis/authen/v1/oidc/access_token"
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "app_id": settings.feishu_app_id,
        "app_secret": settings.feishu_app_secret,
    }

    async with httpx.AsyncClient() as client:
        token_resp = await client.post(token_url, json=payload)
        if token_resp.status_code != 200:
            raise HTTPException(status_code=400, detail="换取 token 失败")
        token_data = token_resp.json()
        if token_data.get("code") != 0:
            raise HTTPException(status_code=400, detail=token_data.get("msg", "token 错误"))

    user_access_token = token_data["data"]["access_token"]
    open_id = token_data["data"]["open_id"]
    name = token_data["data"].get("name", "未知用户")

    # Step 2：（可选）用 user_access_token 获取完整用户信息
    user_info_url = "https://open.feishu.cn/open-apis/authen/v1/user_info"
    headers = {"Authorization": f"Bearer {user_access_token}"}
    async with httpx.AsyncClient() as client:
        info_resp = await client.get(user_info_url, headers=headers)
        info_data = info_resp.json()
        # 可在此查询员工门店 ID（TODO: 对接 HR 系统）

    # Step 3：生成重定向 URL（携带用户身份到飞书小程序前端）
    # 前端拿到这些参数后，在后续请求的 header 中带上
    redirect_url = (
        f"https://example.com/copilotkit?"
        f"open_id={open_id}&"
        f"name={name}"
        # "&store_id=..." 从 HR 系统查
    )

    return RedirectResponse(url=redirect_url, status_code=302)
