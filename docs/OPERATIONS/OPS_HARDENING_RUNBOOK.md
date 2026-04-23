# Ops Hardening Runbook — 门店本体项目 P0

> 来源：昊晴整理 | 作者：谢文龙团队 | 时间：2026-04-22
> 标签：store-ontology, 运维, 安全, 健康检查, 应急
> 描述：store-ontology 项目的运维加固手册，包含健康检查、安全扫描、应急响应

---

## 一、关键路径

| 服务 | 端口 | 健康检查 |
|---|---|---|
| FastAPI 后端 | 8000 | `curl http://localhost:8000/api/health` |
| React 前端 | 3000 | `curl http://localhost:3000` |
| Vite HMR | 5173 | WS 连接（开发模式）|

### 数据目录

| 目录 | 用途 |
|---|---|
| `data/` | ABOX 实例数据（运行时读写）|
| `modules/` | TBOX 本体（只读）|
| `app/data/` | ❌ 已删除（2026-04-22）|

---

## 二、启动与健康检查

### 后端启动

```bash
cd /mnt/d/ObsidianVault/store-ontology
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 前端启动

```bash
cd /mnt/d/ObsidianVault/store-ontology/frontend
npm install  # 首次
npm run dev -- --host 0.0.0.0 --port 3000
```

### 健康检查序列

```bash
# 1. 后端健康
curl -s http://localhost:8000/api/health | jq .

# 2. 前端响应
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000

# 3. 商品 API（验证 DATA_DIR 路径）
curl -s http://localhost:8000/api/reasoning/products | jq 'length'

# 4. TTL 语法验证
rapper -i turtle -o ntriples \
  file:///mnt/d/ObsidianVault/store-ontology/modules/module1-worktask/WORKTASK-MODULE.ttl \
  2>/dev/null | wc -l
# 预期：1256
```

---

## 三、常见故障处理

### 故障 1：Dashboard 左侧无数据

**症状**：`/api/reasoning/products` 返回空或 500

**排查**：
```bash
# 检查 DATA_DIR 路径
grep -n "DATA_DIR" app/routers/reasoning.py
# 确认指向：parent.parent.parent / "data"

# 检查 data/ 目录存在
ls -la data/
# 确认 products.json 在其中

# 检查文件可读
python3 -c "import json; print(len(json.load(open('data/products.json'))['products']))"
```

**根因**：路径曾指向已删除的 `app/data/`

**修复**：见 `app/routers/reasoning.py` 第 14 行

---

### 故障 2：Agent 对话返回 404

**症状**：`POST /api/agent/chat` 返回 404

**排查**：
```bash
# 检查路由注册
grep -n "agent" app/main.py

# 检查 MiniMax API Key
grep -i minimax .env
```

---

### 故障 3：双重渲染（产品列表出现两次）

**症状**：ASCII 柱状图下方出现重复的产品详细行

**排查**：
```bash
# 1. 检查 System Prompt 是否已更新
grep -n "数据展示原则" app/services/agent_executor.py

# 2. 检查前端过滤逻辑
grep -n "品类:" frontend/src/components/ChatAssistant.jsx
```

**修复**：
1. 确认 `agent_executor.py` SYSTEM_PROMPT 已包含数据展示约束
2. 确认 `ChatAssistant.jsx` 有产品行过滤正则
3. 重启前端 Vite dev server：`pkill -f "vite"` 然后重新 `npm run dev`

---

## 四、应急响应

### 事件响应流程

```bash
# 1. 记录事件
python3 .claude/scripts/audit_log.py \
  --step incident \
  --command "incident-response" \
  --goal "<事件摘要>" \
  --status blocked \
  --next-action "调查根因"

# 2. 保存证据
cp -r .planning/audit .planning/audit-backup-$(date +%Y%m%d%H%M%S)

# 3. 回滚（如需要）
git log --oneline -5
git stash  # 未提交的更改
git checkout <last-known-good-sha>
```

---

## 五、安全扫描

### 依赖审计

```bash
# Python 依赖
pip-audit

# Node 依赖
cd frontend && npm audit
```

### 密钥检查

```bash
# 检查 .env 是否包含真实密钥（不应提交）
grep -E "(API_KEY|SECRET|TOKEN)" .env

# 检查 .gitignore 是否包含 .env
grep ".env" .gitignore
```

---

## 六、TTL 本体验证

```bash
# 语法验证（快速）
rapper -i turtle -o ntriples \
  file:///mnt/d/ObsidianVault/store-ontology/modules/module1-worktask/WORKTASK-MODULE.ttl \
  2>/dev/null | wc -l
# 预期：1256

# WebVOWL 可视化
# 打开 https://webvowl.tib.eu/
# 输入 IRI: file:///mnt/d/ObsidianVault/store-ontology/modules/module1-worktask/WORKTASK-MODULE.ttl
```
