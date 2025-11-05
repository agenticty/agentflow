from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv

from .routes import router as base_router          # /api/* (workflows, runs, logs)
from .routes_monitoring import router as monitoring_router

load_dotenv()

if not os.getenv("OPENAI_API_KEY"):
    raise RuntimeError(
        "Missing OPENAI_API_KEY. Set it in .env or environment variables."
    )

app = FastAPI(title="AgentFlow API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://agentflow-tau.vercel.app"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def _dbg(request, call_next):
    print(">>", request.method, request.url.path)
    resp = await call_next(request)
    print("<<", resp.status_code, request.url.path)
    return resp

# Routers
app.include_router(base_router, prefix="/api")
app.include_router(monitoring_router, prefix="/api/monitoring")  

@app.get("/")
def root():
    return {"ok": True, "service": "AgentFlow API"}
