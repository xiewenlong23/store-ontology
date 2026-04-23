# store-ontology

门店自动化运营本体论项目（飞书小程序 + TTL 本体 + AI 对话）

## 项目概述

本体论驱动的"门店大脑"AI应用——飞书小程序为前端，TTL 本体为业务语义层，AI 通过 SPARQL 查询本体 + 推理执行任务。

## 技术栈

- **后端**：Python FastAPI + RDFLib
- **前端**：React + Vite + Tailwind
- **本体**：Turtle (TTL) / OWL2 DL
- **部署**：飞书小程序

---

## 本体论存储结构（TBOX / ABOX）

```
store-ontology/
├── modules/                    # TBOX — 语义存储：本体定义
│   └── module1-worktask/
│       └── WORKTASK-MODULE.ttl   # 临期打折本体（Schema/类/属性/规则）
│
├── data/                       # ABOX — 实例存储：业务数据
│   ├── products.json              # 商品实例
│   └── tasks.json                # 任务实例
│
└── docs/
    ├── TBOX/                  # TBOX — 本体设计文档
    │   ├── README.md
    │   ├── ARCHITECTURE.md
    │   ├── ABOX_TBOX_ARCHITECTURE.md
    │   └── RUNTIME_ADAPTERS.md
    ├── ABOX/                  # ABOX — 实例数据文档（暂无）
    ├── OPERATIONS/            # 运维文档
    ├── AGENT/                 # Agent 系统文档
    └── INFRASTRUCTURE/        # 工程基础设施文档
```

### TBOX / ABOX 职责划分

| 层级 | 目录 | 内容 | 工具 |
|---|---|---|---|
| **TBOX**（语义层） | `modules/` + `docs/TBOX/` | 本体类/属性/OWL声明/推理规则 | Protege, WebVOWL, rapper |
| **ABOX**（实例层） | `data/` + `docs/ABOX/` | 具体商品/任务/库存实例 | SPARQL 查询 |

---

## 代码路径

```
app/                          # FastAPI 后端
├── main.py                   # 入口
├── models.py                 # Pydantic 模型
├── routers/
│   ├── agent.py              # Agent 对话路由
│   ├── tasks.py              # 任务 CRUD
│   ├── reasoning.py          # 推理路由
│   └── pos.py                # POS 模拟器
├── services/
│   ├── agent_executor.py     # Agent 执行器
│   ├── ttl_llm_reasoning.py  # TTL + LLM 推理引擎
│   ├── sparql_service.py     # SPARQL 查询服务
│   ├── llm_service.py        # LLM 调用
│   ├── inventory_service.py  # 库存服务
│   ├── intent_classifier.py  # 意图分类
│   └── auto_confirm_service.py
├── tools/
│   ├── registry.py           # 工具注册表
│   └── store_tools.py        # 门店工具集
└── agent/
    └── store_brain_agent.py  # 门店大脑 Agent

frontend/                     # React 前端
├── src/
│   ├── App.jsx
│   ├── api.js
│   └── components/
│       ├── ChatAssistant.jsx  # AI 对话
│       ├── Dashboard.jsx
│       └── ProductCard.jsx
├── tests/                    # Vitest 测试
└── vite.config.js

tests/                        # Python pytest 测试
├── test_agent.py
├── test_reasoning.py
└── test_integration_*.py
```

---

## FAD 工作流

```
/fad:pipeline <任务>   # 端到端交付
/fad:optimize           # 代码优化
/fad:code review        # 代码审查
```

---

## 常用命令

```bash
# TTL 语法验证
rapper -i turtle -o ntriples file://modules/module1-worktask/WORKTASK-MODULE.ttl

# Python 测试
PYTHONPATH=/mnt/d/ObsidianVault/store-ontology pytest tests/ -v

# 质量门
python3 .claude/scripts/code_quality_gate.py --repo-root .

# 审计日志
python3 .claude/scripts/audit_log.py --step test-step --command "test" --status done --goal "测试"
```

---

## 注意事项

- TTL 本体修改后用 `rapper` 验证语法
- TBOX/ABOX 分离原则：类/属性定义在 `modules/`；业务实例在 `data/`
- 本体迭代方向：LLM Agent 从 one-shot 改为多步循环推理（查询本体 → 决策 → 执行 → 回流 → 再决策）
