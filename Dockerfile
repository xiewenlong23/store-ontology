# ============================================================
# Dockerfile — Phase 7.2
# 生产镜像（多阶段构建）
# ============================================================
FROM python:3.11-slim AS base

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY app/ ./app/
COPY mcp_impl/ ./mcp_impl/
COPY config/ ./config/
COPY ontology/ ./ontology/
COPY scripts/ ./scripts/

# 健康检查
HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=5 \
    CMD curl -sf http://localhost:8000/health || exit 1

EXPOSE 8000

# 启动：先等 GraphDB/PostgreSQL，再启动 MCP，最后启动 uvicorn
CMD ["sh", "-c", "sleep 5 && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
