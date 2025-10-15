import asyncio, os, json, re
from typing import AsyncIterator, Dict, Any, List
from bson import ObjectId
from .db import get_db
from .runtime_agents import map_agent, run_single_task
from .prompt_composer import compose_prompts
from datetime import datetime, timezone

DEMO_MODE = False  # now we run real agents

async def append_log(run_id: str, event: str, data: Dict[str, Any]):
    db = await get_db()
    await db.run_logs.insert_one({
        "run_id": ObjectId(run_id),
        "ts": datetime.now(timezone.utc),
        "event": event,
        "data": data,
    })

async def _get_org() -> dict:
    db = await get_db()
    doc = await db.org.find_one({}) or {}
    # strip Mongo _id for safety
    if "_id" in doc:
        doc = {k: v for k, v in doc.items() if k != "_id"}
    return doc

async def sse_stream(run_id: str) -> AsyncIterator[str]:
    db = await get_db()
    last_id = None
    while True:
        query = {"run_id": ObjectId(run_id)}
        if last_id:
            query["_id"] = {"$gt": last_id}

        cursor = db.run_logs.find(query).sort([("_id", 1)])
        found = False
        async for doc in cursor:
            found = True
            last_id = doc["_id"]
            payload = json.dumps({
                "ts": doc["ts"].replace(tzinfo=timezone.utc).isoformat(),
                "event": doc["event"],
                "data": doc.get("data", {})
            })
            yield f"data: {payload}\n\n"

        # brief idle so we don't spin the CPU while waiting
        await asyncio.sleep(0.4)

# --- minimal templating: {{input.foo}} ---
def render_instructions(tpl: str, inputs: Dict[str, Any]) -> str:
    if not tpl: return ""
    def repl(m):
        key = m.group(1).strip()
        if not key.startswith("input."): return m.group(0)
        path = key.split(".")[1:]
        val = inputs
        for p in path:
            if isinstance(val, dict) and p in val: val = val[p]
            else: return ""
        return str(val)
    return re.sub(r"\{\{\s*([^\}]+)\s*\}\}", repl, tpl)

async def run_workflow(run_id: str):
    """
    Executes a workflow run end-to-end using the Prompt Composer.
    - Fetches org profile and composes prompts for research/qualify/outreach
    - Runs each step sequentially, streaming human-friendly logs
    - Stops early if a step returns: "I can't answer that."
    """
    
    org = await _get_org()
    def _icp_ok(o):
        icp = (o or {}).get("icp", {})
        inds = icp.get("industries", []) or []
        roles = icp.get("roles", []) or []
        return len(inds) + len(roles) >= 2
    if not _icp_ok(org):
        await append_log(run_id, "error", {"message": "Setup incomplete: add industries and roles in Settings."})
        await db.workflow_runs.update_one({"_id": ObjectId(run_id)}, {"$set": {
            "status":"error","finished_at": datetime.now(timezone.utc),"error":"ICP too thin"}})
        return


    db = await get_db()

    # --- load run + workflow + org profile ---
    run = await db.workflow_runs.find_one({"_id": ObjectId(run_id)})
    if not run:
        return
    wf = await db.workflows.find_one({"_id": ObjectId(run["workflow_id"])})
    if not wf:
        return
    org = await db.org.find_one({}) or {}

    inputs = run.get("inputs", {}) or {}

    # Compose default prompts for the standard 3 steps using org+inputs
    prompts = compose_prompts(org, inputs)

    await db.workflow_runs.update_one({"_id": ObjectId(run_id)}, {"$set": {"prompts": prompts}})


    # tiny helpers -------------------------------------------------------------
    def _get_path(src: dict, path: str):
        val = src
        for p in path.split("."):
            if isinstance(val, dict) and p in val:
                val = val[p]
            else:
                return ""
        return val

    def render_with_ctx(tpl: str) -> str:
        """Render {{input.*}} and {{org.*}} inside a user-provided instructions string."""
        if not tpl:
            return ""
        def repl(m):
            expr = m.group(1).strip()
            if expr.startswith("input."):
                return str(_get_path(inputs, expr[len("input."):]) or "")
            if expr.startswith("org."):
                return str(_get_path(org, expr[len("org."):]) or "")
            return m.group(0)
        return re.sub(r"\{\{\s*([^\}]+)\s*\}\}", repl, tpl)
    # -------------------------------------------------------------------------

    outputs = []

    try:
        await append_log(run_id, "started", {"workflow": wf.get("name", "")})

        for i, step in enumerate(wf.get("steps", []), start=1):
            agent_kind = (step.get("agent") or "research").lower()
            user_instr = render_with_ctx(step.get("instructions", "") or "")

            # Choose agent
            agent = map_agent(agent_kind)

            # Pull composed defaults, then prepend any user instructions
            p = prompts.get(agent_kind, {})
            description = ((user_instr + "\n\n") if user_instr else "") + p.get("description", "Produce a concise, useful output.")
            expected    = p.get("expected", "Produce a concise, useful output.")

            await append_log(run_id, "step:start", {
                "index": i,
                "agent": agent_kind,
                "instructions": (user_instr or "")[:240]
            })

            # Include context from the last two steps (if any)
            prev_context = "\n\n".join([o.get("text", "") for o in outputs[-2:]])

            # Run the task (off the event loop)
            text_out = await asyncio.to_thread(
                run_single_task, agent, description, expected, prev_context
            )

    
            # Single log event with all data
            preview = text_out[:600]
            data = {"index": i, "agent": agent_kind, "preview": preview}
            if agent_kind == "outreach":
                data["full"] = text_out
            await append_log(run_id, "step:output", data)

            

            outputs.append({"index": i, "agent": agent_kind, "text": text_out})
            await append_log(run_id, "step:end", {"index": i})

            # Guardrail: stop early on explicit uncertainty
            if isinstance(text_out, str) and "I can't answer that." in text_out:
                await append_log(run_id, "finished", {"status": "stopped"})
                await db.workflow_runs.update_one(
                    {"_id": ObjectId(run_id)},
                    {"$set": {
                        "status": "success",
                        "finished_at": datetime.now(timezone.utc),
                        "output": {"steps": outputs}
                    }}
                )
                return
            
            if agent_kind == "research":
                ok_sources = sum(("openai.com" in o["text"].lower() or "reuters.com" in o["text"].lower()
                                or "bloomberg.com" in o["text"].lower() or "bbc.co.uk" in o["text"].lower()
                                or "apnews.com" in o["text"].lower()) for o in outputs[-1:])
                if ok_sources == 0:
                    await append_log(run_id,"finished",{"status":"stopped"})
                    await db.workflow_runs.update_one({"_id": ObjectId(run_id)},{"$set":{
                        "status":"success","finished_at": datetime.now(timezone.utc),
                        "output":{"steps": outputs, "note":"Stopped: no credible sources"}}})
                    return
                
            
            import json as _json
            if agent_kind == "qualify":
                try:
                    q = _json.loads(text_out)
                except Exception:
                    q = {}
                matches = q.get("criterion_match") or {}
                positives = sum(bool(v) for v in matches.values())
                # cap score if no evidence
                if positives < 2:
                    q["score"] = min(int(q.get("score", 0)), 60)
                    q["decision"] = "maybe" if q["score"] >= 50 else "no"
                    text_out = _json.dumps(q)



        # All steps completed
        await append_log(run_id, "finished", {"status": "success"})
        await db.workflow_runs.update_one(
            {"_id": ObjectId(run_id)},
            {"$set": {
                "status": "success",
                "finished_at": datetime.now(timezone.utc),
                "output": {"steps": outputs}
            }}
        )

    except Exception as e:
        await append_log(run_id, "error", {"message": str(e)})
        await db.workflow_runs.update_one(
            {"_id": ObjectId(run_id)},
            {"$set": {
                "status": "error",
                "finished_at": datetime.now(timezone.utc),
                "error": str(e)
            }}
        )
