# ============================================================
# Makefile — Phase 7.3
# 常用开发/部署命令
# ============================================================

.PHONY: help install test test-unit test-coverage lint \
        up down logs health clean db-init graphdb-init \
        abox-load abox-validate

# ────────────────────────────────────────────────
# 默认帮助
# ────────────────────────────────────────────────
help:
	@echo "Store Ontology — 常用命令"
	@echo ""
	@echo "  make install          安装 Python 依赖"
	@echo "  make test             运行所有测试"
	@echo "  make test-unit        运行单元测试"
	@echo "  make test-coverage    运行测试 + 覆盖率"
	@echo "  make lint             语法检查（py_compile）"
	@echo ""
	@echo "  make up               启动所有服务（docker-compose）"
	@echo "  make down             停止所有服务"
	@echo "  make logs             查看 app 日志"
	@echo "  make health           健康检查"
	@echo "  make clean            清理容器+卷+缓存"
	@echo ""
	@echo "  make db-init          初始化 PostgreSQL Schema"
	@echo "  make graphdb-init     初始化 GraphDB（TBOX+ABOX）"
	@echo "  make abox-load        导入 ABOX 数据"
	@echo "  make abox-validate    验证 ABOX 数据"

# ────────────────────────────────────────────────
# 依赖安装
# ────────────────────────────────────────────────
install:
	pip install -r requirements.txt

# ────────────────────────────────────────────────
# 测试
# ────────────────────────────────────────────────
test:
	pytest tests/ -v

test-unit:
	pytest tests/unit/ -v

test-coverage:
	pytest tests/ --cov=app --cov-report=term-missing --cov-report=html

# ────────────────────────────────────────────────
# 语法检查
# ────────────────────────────────────────────────
lint:
	@echo "检查 Python 语法..."
	@python3 -m py_compile app/main.py && echo "✅ main.py" || echo "❌ main.py"
	@python3 -m py_compile app/config.py && echo "✅ config.py" || echo "❌ config.py"
	@python3 -m py_compile app/agent/state.py && echo "✅ state.py" || echo "❌ state.py"
	@python3 -m py_compile app/agent/deep_agent_factory.py && echo "✅ deep_agent_factory.py" || echo "❌ deep_agent_factory.py"
	@python3 -m py_compile app/agent/interrupts.py && echo "✅ interrupts.py" || echo "❌ interrupts.py"
	@python3 -m py_compile app/agent/tools/__init__.py && echo "✅ tools/__init__.py" || echo "❌ tools/__init__.py"
	@python3 -m py_compile app/agent/tools/sparql_tools.py && echo "✅ sparql_tools.py" || echo "❌ sparql_tools.py"
	@python3 -m py_compile app/agent/tools/discount_tools.py && echo "✅ discount_tools.py" || echo "❌ discount_tools.py"
	@python3 -m py_compile app/agent/tools/mcp_tools.py && echo "✅ mcp_tools.py" || echo "❌ mcp_tools.py"
	@python3 -m py_compile app/audit/audit_service.py && echo "✅ audit_service.py" || echo "❌ audit_service.py"
	@python3 -m py_compile app/audit/logger.py && echo "✅ logger.py" || echo "❌ logger.py"
	@python3 -m py_compile app/observability/langsmith.py && echo "✅ langsmith.py" || echo "❌ langsmith.py"
	@python3 -m py_compile app/observability/tracing.py && echo "✅ tracing.py" || echo "❌ tracing.py"
	@python3 -m py_compile app/auth/roles.py && echo "✅ roles.py" || echo "❌ roles.py"
	@python3 -m py_compile app/integrations/hitl_notifier.py && echo "✅ hitl_notifier.py" || echo "❌ hitl_notifier.py"
	@python3 -m py_compile mcp_impl/erp_mcp.py && echo "✅ erp_mcp.py" || echo "❌ erp_mcp.py"
	@python3 -m py_compile mcp_impl/wms_mcp.py && echo "✅ wms_mcp.py" || echo "❌ wms_mcp.py"
	@python3 -m py_compile mcp_impl/feishu_mcp.py && echo "✅ feishu_mcp.py" || echo "❌ feishu_mcp.py"
	@python3 -m py_compile scripts/load_abox.py && echo "✅ load_abox.py" || echo "❌ load_abox.py"
	@echo "语法检查完成"

# ────────────────────────────────────────────────
# Docker Compose
# ────────────────────────────────────────────────
up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f app

health:
	curl -sf http://localhost:8000/health | python3 -m json.tool

restart:
	docker-compose restart app

# ────────────────────────────────────────────────
# 数据库初始化
# ────────────────────────────────────────────────
db-init:
	@echo "等待 PostgreSQL 就绪..."
	@sleep 5
	docker-compose exec -T postgres psql -U store_user -d store_ontology -f /docker-entrypoint-initdb.d/001_audit_and_hitl.sql
	@echo "✅ PostgreSQL Schema 已初始化"

# ────────────────────────────────────────────────
# GraphDB + ABOX 初始化
# ────────────────────────────────────────────────
graphdb-init:
	@echo "等待 GraphDB 就绪..."
	@docker-compose exec -T app python3 scripts/load_abox.py --dry-run
	@echo "✅ GraphDB 初始化检查完成"

abox-load:
	docker-compose exec app python3 scripts/load_abox.py

abox-validate:
	docker-compose exec app python3 -c 'import asyncio; from app.agent.tools.sparql_tools import query_expiring_products; import json; async def main(): r = await query_expiring_products(\"STORE_001\", 30); print(f"临期商品: {r[\"count\"]} 个"); asyncio.run(main())'

# ────────────────────────────────────────────────
# 清理
# ────────────────────────────────────────────────
clean:
	docker-compose down -v
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name htmlcov -exec rm -rf {} + 2>/dev/null || true
	@echo "清理完成"
