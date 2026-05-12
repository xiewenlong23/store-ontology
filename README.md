# Store Ontology — 门店大脑 AI 原生应用

> 基于 Deep Agents + LangGraph + CopilotKit + 本体论的零售门店智能决策系统

## 架构

```
飞书小程序（CopilotKit 前端）
        ↕
FastAPI（CopilotKitRemoteEndpoint + Deep Agents）
        ↕
┌───────────────────────────────────────────────┐
│  Deep Agents Agent（Skill 运行时）            │
│    ├── discount-skill（折扣推荐）             │
│    ├── task-skill（任务管理）                 │
│    ├── product-skill（商品查询）             │
│    ├── inventory-skill（库存预警）            │
│    └── display-skill（陈列优化）             │
└───────────────────────────────────────────────┘
        ↕
  SPARQL 查询        MCP 工具（外部系统）
        ↕                  ↕
  GraphDB           ERP / WMS / 飞书
```

## 目录结构

```
store-ontology/
├── app/
│   ├── agent/          # Deep Agents + LangGraph 运行时
│   │   ├── state.py    # AgentState（继承 CopilotKitState）
│   │   ├── deep_agent_factory.py
│   │   ├── interrupts.py
│   │   └── tools/       # 工具注册表 + 各 Skill 工具
│   ├── auth/            # 角色权限判断
│   ├── audit/           # 审计日志（structlog + PostgreSQL）
│   ├── observability/   # LangSmith + 链路追踪
│   ├── integrations/    # 飞书通知 + HITL 审批卡片
│   └── main.py          # FastAPI 入口
├── config/              # YAML 配置文件（业务规则外置）
│   ├── skills.yaml      # Skill allowed-tools
│   ├── roles.yaml       # 角色权限矩阵
│   ├── hitl.yaml        # HITL 审批规则
│   └── mcp.yaml         # MCP Server 配置
├── mcp_impl/            # MCP Server 实现（erp / wms / feishu）
├── ontology/
│   ├── tbox/            # TBOX 本体论（TTL 模块）
│   └── abox/            # ABOX 实例数据
├── scripts/
│   ├── load_abox.py     # TBOX+ABOX 导入 GraphDB
│   └── migrations/       # PostgreSQL Schema
├── tests/               # 单元测试 + 集成测试
└── docker-compose.yml
```

## 快速启动

### 1. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 填入真实密钥
```

### 2. 启动服务

```bash
# 启动所有服务（PostgreSQL + GraphDB + App）
docker-compose up -d

# 查看日志
docker-compose logs -f app

# 健康检查
curl http://localhost:8000/health
```

### 3. 搭建 Python 环境

```bash
# 创建 conda 环境（与 pytorch_gpu 环境分离）
conda create -n store-ontology python=3.11 -y
conda activate store-ontology

# 安装依赖（requirements.txt 中已修正版本约束）
pip install -r requirements.txt
```

### 4. 启动服务

```bash
# 启动 PostgreSQL + GraphDB（Docker）
docker-compose up -d postgres graphdb

# 导入本体数据
python scripts/load_abox.py

# 启动 FastAPI
uvicorn app.main:app --reload --port 8000
```

## 环境变量

| 变量 | 必填 | 说明 |
|------|------|------|
| `STORE_ID` | ✅ | 门店编号 |
| `FEISHU_BOT_TOKEN` | ✅ | 飞书 Bot Token |
| `FEISHU_APP_ID` | ✅ | 飞书 App ID |
| `FEISHU_APP_SECRET` | ✅ | 飞书 App Secret |
| `SPARQL_ENDPOINT` | ✅ | GraphDB SPARQL 端点 |
| `DATABASE_URL` | ✅ | PostgreSQL 连接字符串 |
| `LANGSMITH_API_KEY` | ❌ | LangSmith（不填则停用） |
| `ERP_API_KEY` | ❌ | ERP 系统（Mock 时不填） |
| `WMS_API_KEY` | ❌ | WMS 系统（Mock 时不填） |

## 测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行单元测试
pytest tests/unit/ -v

# 运行覆盖率报告
pytest tests/ --cov=app --cov-report=html
```

### Playwright E2E 测试

```bash
# 1. 安装 Python Playwright 环境（一次性）
uv venv /tmp/pw_env --python 3.12
/tmp/pw_env/bin/python3.12 -m pip install playwright -q
/tmp/pw_env/bin/python3.12 -m playwright install chromium

# 2. 启动后端和前端
uvicorn app.main:app --port 8000 &
npm run dev  # localhost:3000

# 3. 运行 E2E 测试
/tmp/pw_env/bin/python3.12 tests/e2e/playwright_test.py
```

截图自动保存到 `/tmp/store-ontology-e2e/`

## 接口文档

启动后访问：
- FastAPI Swagger UI：http://localhost:8000/docs
- GraphDB Workbench：http://localhost:7200
- LangSmith Dashboard：（如有配置）

## Phase 说明

| Phase | 内容 |
|-------|------|
| Phase 1 | CopilotKit 前端集成 |
| Phase 2 | Deep Agents 后端 + discount-skill |
| Phase 3 | GraphDB + TTL 本体 + SPARQL |
| Phase 4 | HITL 审批流 + 权限矩阵 |
| Phase 5 | 审计日志 + LangSmith |
| Phase 6 | MCP Server（ERP/WMS/飞书）|
| Phase 7 | 测试 + 部署 |
