from fastapi import FastAPI
from app.routers import tasks, reasoning

app = FastAPI(title="Store-Ontology API", version="1.0.0")

app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
app.include_router(reasoning.router, prefix="/api/reasoning", tags=["reasoning"])

@app.get("/api/health")
def health():
    return {"status": "ok"}
