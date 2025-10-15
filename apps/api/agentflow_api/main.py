from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv

from .routes import router as base_router          # /api/* (workflows, runs, logs)
from .route.agents import router as agents_router  # /api/agents/* (your agent endpoints)

load_dotenv()

if not os.getenv("OPENAI_API_KEY"):
    raise RuntimeError(
        "Missing OPENAI_API_KEY. Set it in .env or environment variables."
    )

app = FastAPI(title="AgentFlow API", version="0.2.0")

# CORS
frontend_origin = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_origin, "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# DB-free health (never hangs)
@app.get("/healthz")
def healthz():
    return {"ok": True}

@app.get("/api/health")
def api_health():
    return {"ok": True, "service": "AgentFlow API"}

# (Optional) tiny tracer while debugging
@app.middleware("http")
async def _dbg(request, call_next):
    print(">>", request.method, request.url.path)
    resp = await call_next(request)
    print("<<", resp.status_code, request.url.path)
    return resp

# Routers
app.include_router(base_router, prefix="/api")   # e.g., /api/workflows, /api/workflow-runs
app.include_router(agents_router)                # already has prefix="/api/agents"

@app.get("/")
def root():
    return {"ok": True, "service": "AgentFlow API"}
