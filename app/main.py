"""
Store Ontology - FastAPI Entry Point
Phase 1.1: 飞书账号绑定 + CopilotKit User Identity
Phase 1.5: 飞书推送通知集成
Phase 2.1: CopilotKitRemoteEndpoint + Deep Agents
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from copilotkit import CopilotKitRemoteEndpoint
from app.config import settings
from app.integrations.feishu_identity import resolve_copilotkit_user
from app.integrations.feishu_notifier import router as feishu_router
from app.integrations.feishu_oauth import router as feishu_auth_router
from app.agent.deep_agent_factory import create_store_brain_agent

app = FastAPI(
    title="Store Ontology API",
    description="零售门店 AI 助手 - CopilotKit Runtime + 本体知识图谱",
    version="1.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# CopilotKit Remote Endpoint（Phase 2.1）
# 生产部署用 RemoteEndpoint，接收飞书小程序前端请求
# ============================================================
async def get_copilotkit_agents(context: dict):
    """
    每次请求根据用户身份创建对应的 Agent 实例

    context 来自 CopilotKitRemoteEndpoint，包含：
      - properties.user_id
      - properties.store_id
      - properties.role
      - properties.authorization
    """
    props = context.get("properties", {})
    user_id = props.get("user_id", "")
    store_id = props.get("store_id", "STORE_001")
    role = props.get("role", "clerk")
    auth_token = props.get("authorization", "")

    return [
        create_store_brain_agent(
            user_id=user_id,
            store_id=store_id,
            role=role,
            employee_name=props.get("user_name", ""),
            auth_token=auth_token,
        )
    ]


sdk = CopilotKitRemoteEndpoint(agents=get_copilotkit_agents)
sdk.mount(app, "/api/copilotkit")


# ============================================================
# 飞书路由
# ============================================================
app.include_router(feishu_router)      # Phase 1.5
app.include_router(feishu_auth_router)  # Phase 1.1


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "store_id": settings.store_id,
        "version": "1.0.0",
    }


@app.get("/")
async def root():
    return {
        "message": "门店大脑 AI 助手",
        "docs": "/docs",
        "health": "/health",
    }
