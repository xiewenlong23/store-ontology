# store-ontology

门店自动化运营本体论项目（飞书小程序 + TTL 本体 + AI 对话）

## 项目概述

本体论驱动的"门店大脑"AI应用——飞书小程序为前端，TTL 本体为业务语义层，AI 通过 SPARQL 查询本体 + 推理执行任务。

## 技术栈

- **后端**：Python FastAPI + RDFLib
- **前端**：React + Vite
- **本体**：Turtle (TTL) / OWL2 DL
- **数据**：JSON 配置文件
- **部署**：飞书小程序

## 关键路径

```
app/                    # FastAPI 后端
  routers/
    tasks.py          # 任务 CRUD
    reasoning.py      # 对话 + 推理
  main.py             # FastAPI 入口
  models.py           # Pydantic 模型
  data/
    products.json     # 商品数据
    tasks.json        # 任务数据

modules/               # TTL 本体模块
  module1-worktask/
    WORKTASK-MODULE.ttl  # 临期打折本体（1256 triples）

examples/
  clearance_engine.py  # TTL 推理引擎（CLI）
  DEMO-DISCOUNT-001.ttl # 示例实例数据
  products.json         # 示例商品

frontend/src/          # React 前端
  components/
    ChatAssistant.jsx  # AI 对话组件
    ProductCard.jsx    # 商品卡片
  api.js              # API 调用

validation/
  validate_ontology.py  # TTL 验证脚本
```

## FAD 工作流

```
/fad:pipeline <任务>   # 端到端交付
/fad:optimize          # 代码优化
/review                # 代码审查
```

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

## 注意事项

- TTL 本体修改后用 `rapper` 验证语法
- FastAPI 路由已配置 Vite 代理（开发环境），生产需配 CORS
- clearance_engine.py 假设从 `examples/` 目录运行
