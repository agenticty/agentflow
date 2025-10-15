from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from typing import List
from datetime import datetime
import asyncio
from .db import get_db
from .models import CreateWorkflowRequest, Workflow, CreateRunRequest, WorkflowRun
from bson import ObjectId
from .orchestrator import sse_stream, run_workflow
from .runtime_agents import make_researcher, run_single_task
import json, re, asyncio

router = APIRouter()

# api/agentflow_api/routes.py
@router.get("/debug/db")
async def debug_db():
    from .db import get_db
    import os
    db = await get_db()
    return {
      "MONGODB_URI": os.getenv("MONGODB_URI", "")[:40] + "…",
      "MONGODB_DB": os.getenv("MONGODB_DB", ""),
      "counts": {
        "org": await db.org.count_documents({}),
        "workflows": await db.workflows.count_documents({}),
      },
    }

@router.get("/org/profile")
async def get_org_profile():
    db = await get_db()
    doc = await db.org.find_one({}) or {}
    # compute readiness once, here
    def is_ready(d: dict) -> bool:
        name_ok = bool(d.get("name", "").strip())
        one_ok  = bool(d.get("product_one_liner", "").strip())
        vps_ok  = bool(d.get("value_props")) and len(d["value_props"]) > 0
        icp     = d.get("icp") or {}
        icp_ok  = any([
            bool(icp.get("industries")),
            bool(icp.get("roles")),
            bool(icp.get("regions")),
            bool(icp.get("tech_signals")),
        ])
        # be reasonable: name + one-liner + (some ICP or some value props)
        return name_ok and one_ok and (vps_ok or icp_ok)

    doc_out = {k: v for k, v in doc.items() if k != "_id"}
    doc_out["ready"] = is_ready(doc_out)
    return doc_out

@router.post("/org/profile")
async def upsert_org_profile(profile: dict):
    if not isinstance(profile, dict):
        raise HTTPException(status_code=400, detail="Invalid payload")
    db = await get_db()
    exists = await db.org.find_one({})
    if exists:
        await db.org.update_one({"_id": exists["_id"]}, {"$set": profile})
    else:
        await db.org.insert_one(profile)
    return {"ok": True}


@router.get("/health")
async def health():
    db = await get_db()
    names = await db.list_collection_names()
    return {"ok": True, "collections": names}

@router.post("/org/from-url")
async def org_from_url(payload: dict):
    import asyncio, re, json, requests
    url = (payload or {}).get("url","").strip()
    if not url:
        raise HTTPException(status_code=400, detail="Missing url")

    # 1) Fast fetch (8s timeout) + light clean
    try:
        r = requests.get(url, timeout=8, headers={"User-Agent":"Mozilla/5.0"})
        r.raise_for_status()
        html = r.text
    except Exception as e:
        return {"draft": None, "warning": f"Could not fetch site: {e}"}

    # 2) Heuristic extract (no LLM yet)
    def tag(rx, default=""):
        m = re.search(rx, html, re.I|re.S)
        return (m.group(1).strip() if m else default)[:240]
    title = tag(r"<title>(.*?)</title>")
    desc  = tag(r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']')
    h1    = tag(r"<h1[^>]*>(.*?)</h1>")

    # 3) Build a minimal, safe draft
    base_name = re.sub(r"\s*\|.*$","", title).strip() or re.sub(r"^https?://(www\.)?","", url).split("/")[0]
    one_liner = desc or h1 or title
    draft = {
        "name": base_name[:80],
        "product_one_liner": one_liner[:160],
        "value_props": [],
        "icp": {
            "industries": [],
            "employee_range": {"min": 0, "max": 1000000},
            "regions": [],
            "roles": [],
            "tech_signals": []
        }
    }

    # 4) OPTIONAL: one short LLM pass (hard 6s) to propose value props (skip if you prefer)
    try:
        async def llm():
            from .agents import make_researcher, run_single_task
            agent = make_researcher()
            desc = ("From this snippet, propose 2-3 short value props as a JSON array of strings. "
                    "Return JSON only.\n\nSNIPPET:\n" + (desc or h1 or title))
            expected = "JSON array only."
            return await asyncio.to_thread(run_single_task, agent, desc, expected, "")
        props = await asyncio.wait_for(llm(), timeout=6.0)
        m = re.search(r"\[(.|\n|\r)*\]$", props)
        if m:
            arr = json.loads(m.group(0))
            if isinstance(arr, list):
                draft["value_props"] = [str(x)[:80] for x in arr[:3]]
    except Exception:
        pass  # keep draft minimal

    return {"draft": draft, "warning": None}


@router.post("/workflows", response_model=Workflow)
async def create_workflow(payload: CreateWorkflowRequest):
    db = await get_db()
    doc = payload.model_dump()
    res = await db.workflows.insert_one(doc)
    doc["_id"] = res.inserted_id
    return {
        "id": str(doc["_id"]),
        "name": doc["name"],
        "trigger": doc["trigger"],
        "steps": doc["steps"],
    }

@router.get("/workflows", response_model=List[Workflow])
async def list_workflows():
    db = await get_db()
    cursor = db.workflows.find({})
    items = []
    async for d in cursor:
        items.append({
            "id": str(d["_id"]),
            "name": d["name"],
            "trigger": d["trigger"],
            "steps": d["steps"],
        })
    return items


@router.delete("/workflows/{workflow_id}")
async def delete_workflow(workflow_id: str):
    db = await get_db()
    res = await db.workflows.delete_one({"_id": ObjectId(workflow_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    return {"ok": True}

@router.post("/workflow-runs", response_model=WorkflowRun)
async def create_run(payload: CreateRunRequest):
    inputs = payload.inputs or {}
    if not inputs.get("company", "").strip():
        raise HTTPException(
            status_code=400,
            detail="Missing required input: company"
        )
    db = await get_db()
    wf = await db.workflows.find_one({"_id": ObjectId(payload.workflow_id)})
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")

    doc = {
        "workflow_id": ObjectId(payload.workflow_id),
        "status": "running",
        "started_at": datetime.utcnow(),
        "finished_at": None,
        "output": None,
        "error": None,
        "inputs": payload.inputs or {},
    }
    res = await db.workflow_runs.insert_one(doc)
    run_id = str(res.inserted_id)

    # fire-and-forget execution
    asyncio.create_task(run_workflow(run_id))

    return WorkflowRun(id=run_id, workflow_id=payload.workflow_id, status="running")

@router.get("/workflow-runs/{run_id}/logs")
async def stream_logs(run_id: str, request: Request):
    async def event_generator():
        async for chunk in sse_stream(run_id):
            # Client disconnect?
            if await request.is_disconnected():
                break
            yield chunk
    return StreamingResponse(event_generator(), media_type="text/event-stream")
