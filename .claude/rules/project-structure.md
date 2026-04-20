# Project Structure Rules

## 目录结构

```
store-ontology/
├── app/                    # FastAPI 后端
│   ├── __init__.py
│   ├── main.py            # FastAPI 入口
│   ├── models.py          # Pydantic models
│   ├── data/              # JSON 数据文件
│   │   ├── products.json
│   │   └── tasks.json
│   └── routers/           # API 路由
│       ├── __init__.py
│       ├── tasks.py
│       └── reasoning.py
├── frontend/              # React 前端
│   ├── src/
│   │   ├── components/   # React 组件
│   │   ├── api.js        # API 调用
│   │   └── App.jsx       # 根组件
│   ├── package.json
│   └── vite.config.js
├── modules/              # TTL 本体模块
│   └── module1-worktask/
│       └── WORKTASK-MODULE.ttl
├── examples/             # 示例和规则引擎
├── validation/          # 本体验证工具
├── tests/              # 测试文件
├── .claude/            # Claude Code 配置
└── CLAUDE.md           # 项目说明
```

## 模块职责

| 目录 | 职责 |
|-----|------|
| `app/` | API、业务逻辑、数据模型 |
| `frontend/` | UI 展示、用户交互 |
| `modules/` | 本体定义（OWL/Turtle） |
| `examples/` | 示例数据、规则引擎 |
| `validation/` | 本体验证 |

## 文件命名
- Python: `snake_case.py`
- React: `PascalCase.jsx`
- 配置: `kebab-case.json`
- 本体: `UPPER-CASE-MODULE.ttl`
