# store-ontology

AI 门店大脑 — 临期商品管理系统。基于 FastAPI + Deep Agents + CopilotKit + Next.js。

> 详细设计见 [docs/design/README.md](docs/design/README.md)。

## 环境要求

- **Python 3.11+**（推荐 conda 环境：`store-ontology`，位于 `/opt/miniconda3/envs/store-ontology`）
- **Node.js 20+**（项目验证用 v24.6.0）
- 后端 LLM Key：MiniMax / Qwen 兼容 OpenAI 的 API

## 启动

### 1. 后端（端口 8123）

```bash
conda activate store-ontology
cd agent
# 首次启动需要填入 QWEN_API_KEY（见项目根 .env）
python main.py
```

健康检查：`curl http://localhost:8123/health` → `{"status":"healthy"}`

### 2. 前端（端口 3000）

```bash
cd frontend
npm install        # 首次或 lockfile 变更时执行
npm run dev
```

打开 http://localhost:3000

## 项目结构

```
store-ontology/
├── agent/                # FastAPI + Deep Agents（Agent 平台层）
│   ├── main.py           # 入口（端口 8123）
│   ├── engine/           # 核心引擎（parser/executor/repository/pack/workspace_bootstrap/tenant）
│   ├── tools/            # 系统原子 Tool（query/crud/action + shared 装配）
│   └── skills/           # 系统 Skill（platform-help，所有 workspace 共享）
├── workspace/            # Workspace 层（行业包 + 客户实例）
│   ├── retail/           # 零售行业基础包（只读模板）
│   │   ├── ontology/domains/   # 本体声明（domain.ttl + actions/*.yaml）
│   │   ├── data/              # 种子数据
│   │   └── skills/            # 自包含场景单元（SKILL.md + tools.py + state_machine.py）
│   ├── equipment_repair/ # 设备维修行业包
│   └── customer_default/ # 默认客户实例
├── frontend/             # Next.js 15 + CopilotKit 1.57
│   └── app/api/copilotkit/   # AG-UI 代理（注入 X-Workspace header）
└── docs/                 # 设计文档
```

## 环境配置

项目根目录 `.env`（已在 .gitignore，提交时不会泄露）：

```env
QWEN_API_KEY=<your_key>
QWEN_BASE_URL=https://api.minimaxi.com/v1
QWEN_MODEL=MiniMax-M2.7-highspeed
```

仓库根目录有 `.env.example` 作为模板。

## 端口速查

| 服务 | 端口 |
|---|---|
| FastAPI 后端 | 8123 |
| Next.js 前端 | 3000 |

## 常见问题

- **缺 `QWEN_API_KEY`**：启动后端会报 `RuntimeError`，去项目根 `.env` 填入。
- **端口被占用**：`lsof -nP -iTCP:8123 -sTCP:LISTEN` 查 PID，杀掉或改 `PORT` 环境变量。
- **前端 CopilotKit 404**：检查前端 `app/api/copilotkit/route.ts` 是否代理到 `http://localhost:8123/api/copilotkit`。
