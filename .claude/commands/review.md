---
name: review
description: 严重级别优先的代码审查
argument-hint: "[可选：文件路径、模块或变更范围]"
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
  - Task
---

<objective>
将审查作为风险检测工作流，而非风格检查清单。
</objective>

<context>
项目：store-ontology（门店自动化运营本体）
根目录：/mnt/d/ObsidianVault/store-ontology

技术栈：
- 后端：Python (FastAPI) + RDFLib
- 前端：React + Vite
- 本体：TTL/RDF (OWL2 DL)
- 数据：JSON 配置文件

审查重点：
- TTL 本体结构和 OWL 语义正确性
- FastAPI 路由、CORS、错误处理
- React 组件状态和 API 调用
- 意图识别和对话逻辑
</context>

<process>
## 审查范围
根据 staged changes 或提供的路径/模块确定审查范围。

## 严重级别定义

### 🔴 Critical（阻塞级）
- CORS 未配置导致 API 无法跨域调用
- 关键业务逻辑缺失（如 mock 数据代替真数据）
- 文件不存在导致 500 错误无处理
- 安全漏洞（敏感数据暴露、注入风险）

### 🟡 Important（重要）
- TTL 本体结构错误（逆属性缺失、domain/range 错误）
- 硬编码日期或测试数据
- 缺少边界校验
- 意图识别过于简陋
- 数据不一致（接口 vs JSON）

### 🟢 Minor（轻微）
- 空 `__init__.py` 文件
- 重复 import
- 硬编码端口
- 缺少 `useMemo`/`useCallback` 优化

## 审查流程

### Pass 1：Critical 问题扫描
1. 检查 `app/main.py` 是否配置 CORS
2. 检查文件读取是否有 `try/except` 和友好错误提示
3. 检查 mock 数据 vs 真实数据是否一致
4. 检查前端 API 调用是否有错误处理

### Pass 2：Important 问题扫描
1. TTL 本体验证（`rapper` 语法检查）
2. 硬编码日期/路径检查
3. 边界校验检查
4. 意图识别健壮性检查

### Pass 3：Minor 问题扫描
1. 代码重复
2. 空文件
3. import 重复

## 审查输出格式

```
## Review 结果 — <范围>

### 🔴 Critical
| # | 文件 | 问题 | 修复建议 |
|---|------|------|----------|
| 1 | app/routers/reasoning.py | ... | ... |

### 🟡 Important
...

### 🟢 Minor
...

### 优先修复建议
1. ...
2. ...
```

## 修复策略
- **机械性低风险** → 自动修复
- **模糊/高风险** → 标记 NEEDS INPUT，等待人工决策
