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

    def _has_preloaded_site(pre_ctx: str) -> bool:
        return "##COMPANY WEBSITE CONTENT##" in (pre_ctx or "")



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

            
            if agent_kind == "research":
                
                website = inputs.get("website", "").strip()
                company = inputs.get("company", "").strip()
                
                pre_context = prev_context
                if website:
                    await append_log(run_id, "fetching_website", {
                        "index": i,
                        "url": website,
                        "reason": "Using provided website as primary source"
                    })
                    
                    from .runtime_agents import clean_url
                    try:

                        website_content = clean_url._run(website)

                        if "Download failed" or "No extractable text" not in website_content:
                            pre_context = (
                                "##COMPANY WEBSITE CONTENT##\n"
                                f"{website_content}\n"
                                "##END COMPANY WEBSITE CONTENT##\n\n"
                                f"{prev_context}"
                            )
                            await append_log(run_id, "website_fetched", {
                                "index": i,
                                "status": "success",
                                "length": len(website_content)
                            })
                    except Exception as e:
                        await append_log(run_id, "website_fetch_failed", {
                            "index": i,
                            "error": str(e)
                        })
                
                # Run research with website content pre-loaded
                text_out = await asyncio.to_thread(
                    run_single_task, agent, description, expected, pre_context
                )
            else:
                # Non-research tasks: normal execution
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

            if agent_kind == "research":
                await append_log(run_id, "debug", {
                    "raw_output": text_out,
                    "length": len(text_out),
                    "has_urls": "http" in text_out.lower(),
                    "has_cant_answer": "can't answer" in text_out.lower()
                })

            
            
            
            if agent_kind == "research":
                # Import the scoring function
                from .runtime_agents import score_research_quality
                
                # Score the research quality
                quality_score = score_research_quality(text_out)
                
                # Log the quality assessment
                await append_log(run_id, "research:quality", {
                    "index": i,
                    "confidence": quality_score["confidence"],
                    "quality": quality_score["quality"],
                    "sources": {
                        "tier1": quality_score["tier1_sources"],
                        "tier2": quality_score["tier2_sources"],
                        "total_credible": quality_score["total_credible"],
                        "total_found": quality_score["total_urls"]
                    }
                })
                
                # Stop if quality is too low
                if not quality_score["passed"]:
                    reason = f"Research confidence too low ({quality_score['confidence']}%)"
                    detail_parts = []
                    
                    if quality_score["total_credible"] == 0:
                        detail_parts.append("No credible sources found")
                    else:
                        detail_parts.append(f"Found {quality_score['total_credible']} credible source(s), need 2+ high-quality")
                    
                    if quality_score["total_urls"] > 0:
                        detail_parts.append(f"Checked {quality_score['total_urls']} URLs total")
                    
                    detail = " • ".join(detail_parts)
                    
                    await append_log(run_id, "finished", {
                        "status": "stopped",
                        "reason": reason,
                        "detail": detail,
                        "recommendation": "Manual research recommended - try alternative sources or verify company name"
                    })
                    
                    await db.workflow_runs.update_one(
                        {"_id": ObjectId(run_id)},
                        {"$set": {
                            "status": "stopped_low_quality",
                            "finished_at": datetime.utcnow(),
                            "output": {
                                "steps": outputs,
                                "stop_reason": reason,
                                "quality_score": quality_score
                            }
                        }}
                    )
                    return
            
            
            import json as _json
            if agent_kind == "qualify":
                try:
                    q = _json.loads(text_out)
                except Exception:
                    q = {"score": 0, "decision": "no", "reasons": ["Invalid qualification format"]}
                
                # Enhanced qualification validation
                matches = q.get("criterion_match") or {}
                reasons = q.get("reasons") or []
                score = int(q.get("score", 0))
                
                # Count how many ICP criteria are met
                positives = sum(bool(v) for v in matches.values())
                
                # Adjust score based on evidence strength
                if positives < 2:
                    # Not enough evidence - cap score
                    score = min(score, 60)
                    q["score"] = score
                    q["decision"] = "maybe" if score >= 50 else "no"
                    if "Low evidence count" not in " ".join(reasons):
                        q["reasons"].append(f"Only {positives} ICP criterion clearly matched (need 2+)")
                
                # Add confidence indicator
                if positives >= 4 and score >= 80:
                    q["confidence"] = "high"
                elif positives >= 3 and score >= 65:
                    q["confidence"] = "medium"
                elif positives >= 2 and score >= 50:
                    q["confidence"] = "low"
                else:
                    q["confidence"] = "insufficient"
                
                text_out = _json.dumps(q, indent=2)
                
                # Log qualification quality
                await append_log(run_id, "qualify:assessed", {
                    "index": i,
                    "score": q["score"],
                    "decision": q["decision"],
                    "confidence": q.get("confidence", "unknown"),
                    "criteria_matched": positives,
                    "total_criteria": len(matches)
                })
                
                # Stop if decisively disqualified
                if q["decision"] == "no" and q["score"] < 40:
                    await append_log(run_id, "finished", {
                        "status": "stopped",
                        "reason": f"Lead disqualified (score: {q['score']}/100)",
                        "detail": " • ".join(q["reasons"][:3]),  # Top 3 reasons
                        "recommendation": "Does not match ICP - skip outreach"
                    })
                    
                    await db.workflow_runs.update_one(
                        {"_id": ObjectId(run_id)},
                        {"$set": {
                            "status": "disqualified",
                            "finished_at": datetime.utcnow(),
                            "output": {
                                "steps": outputs,
                                "qualification": q
                            }
                        }}
                    )
                    return



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
