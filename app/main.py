from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import tasks, reasoning, agent, pos, staff
from dotenv import load_dotenv
load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        from app.services.scheduler_service import init_scheduler
        init_scheduler()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Scheduler init failed: {e}")
    yield
    # Shutdown
    try:
        from app.services.scheduler_service import shutdown_scheduler
        shutdown_scheduler()
    except Exception:
        pass

app = FastAPI(title="Store-Ontology API", version="1.0.0", lifespan=lifespan)

# CORS configuration — allow frontend dev server
# Support CORS_ORIGINS env var as comma-separated list
import os
_cors_env = os.environ.get("CORS_ORIGINS", "")
if _cors_env:
    _cors_origins = [o.strip() for o in _cors_env.split(",") if o.strip()]
else:
    _cors_origins = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
app.include_router(staff.router, prefix="/api/staff", tags=["staff"])
app.include_router(reasoning.router, prefix="/api/reasoning", tags=["reasoning"])
app.include_router(agent.router, prefix="/api/agent", tags=["agent"])
app.include_router(pos.router, prefix="/api/pos", tags=["pos"])

@app.get("/api/health")
def health():
    return {"status": "ok"}
