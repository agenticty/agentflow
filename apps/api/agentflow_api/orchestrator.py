# apps/api/agentflow_api/orchestrator.py
import asyncio, os, json, re
from typing import AsyncIterator, Dict, Any, List
from bson import ObjectId
from .db import get_db
from .runtime_agents import map_agent, run_single_task, RateLimitError
from .prompt_composer import compose_prompts
from datetime import datetime, timezone
from .rate_limiter import (
    workflow_limiter, 
    openai_circuit_breaker,
    retry_with_backoff,
    RetryConfig
)
import logging

logger = logging.getLogger(__name__)

DEMO_MODE = False

# Retry configuration for agent tasks
AGENT_RETRY_CONFIG = RetryConfig(
    max_retries=2,  # Retry twice for transient failures
    base_delay=2.0,
    max_delay=30.0,
    exponential_base=2.0,
    jitter=True
)


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
    if "_id" in doc:
        doc = {k: v for k, v in doc.items() if k != "_id"}
    return doc


async def sse_stream(run_id: str) -> AsyncIterator[str]:
    """Stream workflow execution logs via Server-Sent Events."""
    db = await get_db()
    last_id = None
    
    # Add timeout to prevent infinite streaming
    start_time = datetime.now(timezone.utc)
    max_duration = 600  # 10 minutes max
    
    while True:
        # Check if we've exceeded max duration
        elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
        if elapsed > max_duration:
            logger.warning(f"SSE stream timeout for run {run_id}")
            yield f"data: {json.dumps({'event': 'timeout', 'data': {'message': 'Stream timeout'}})}\n\n"
            break
        
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
            
            # If workflow finished, stop streaming
            if doc["event"] in ("finished", "error"):
                logger.debug(f"SSE stream ending for run {run_id}: {doc['event']}")
                return

        await asyncio.sleep(0.4)


@retry_with_backoff(
    config=AGENT_RETRY_CONFIG,
    exceptions=(RateLimitError, ConnectionError, TimeoutError)
)
async def _run_agent_with_retry(
    agent, 
    description: str, 
    expected: str, 
    context: str
) -> str:
    """
    Run agent task with automatic retry for rate limits and transient errors.
    """
    try:
        # Use circuit breaker for OpenAI calls
        result = await openai_circuit_breaker.call(
            asyncio.to_thread,
            run_single_task,
            agent,
            description,
            expected,
            context
        )
        return result
    except Exception as e:
        logger.error(f"Agent execution error: {e}")
        raise


async def run_workflow(run_id: str):
    """
    Executes a workflow run end-to-end with rate limiting and error handling.
    - Enforces concurrent workflow limits
    - Retries transient failures
    - Uses circuit breaker for OpenAI API
    - Stops early on quality gates
    """
    
    # Enforce concurrent workflow limit
    try:
        async with workflow_limiter:
            await _run_workflow_impl(run_id)
    except asyncio.TimeoutError:
        db = await get_db()
        await append_log(run_id, "error", {
            "message": "Workflow timeout - too many concurrent workflows"
        })
        await db.workflow_runs.update_one(
            {"_id": ObjectId(run_id)},
            {"$set": {
                "status": "error",
                "finished_at": datetime.now(timezone.utc),
                "error": "Workflow limiter timeout"
            }}
        )


async def _run_workflow_impl(run_id: str):
    """Internal workflow implementation with full error handling."""
    
    db = await get_db()
    
    try:
        # Validate org profile
        org = await _get_org()
        def _icp_ok(o):
            icp = (o or {}).get("icp", {})
            inds = icp.get("industries", []) or []
            roles = icp.get("roles", []) or []
            return len(inds) + len(roles) >= 2
        
        if not _icp_ok(org):
            await append_log(run_id, "error", {
                "message": "Setup incomplete: add industries and roles in Settings."
            })
            await db.workflow_runs.update_one(
                {"_id": ObjectId(run_id)},
                {"$set": {
                    "status": "error",
                    "finished_at": datetime.now(timezone.utc),
                    "error": "ICP too thin"
                }}
            )
            return

        # Load run + workflow
        run = await db.workflow_runs.find_one({"_id": ObjectId(run_id)})
        if not run:
            logger.error(f"Run {run_id} not found")
            return
        
        wf = await db.workflows.find_one({"_id": ObjectId(run["workflow_id"])})
        if not wf:
            logger.error(f"Workflow {run['workflow_id']} not found")
            return

        inputs = run.get("inputs", {}) or {}
        
        # Compose prompts
        prompts = compose_prompts(org, inputs)
        await db.workflow_runs.update_one(
            {"_id": ObjectId(run_id)},
            {"$set": {"prompts": prompts}}
        )

        # Helper functions
        def _get_path(src: dict, path: str):
            val = src
            for p in path.split("."):
                if isinstance(val, dict) and p in val:
                    val = val[p]
                else:
                    return ""
            return val

        def render_with_ctx(tpl: str) -> str:
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

        outputs = []
        await append_log(run_id, "started", {"workflow": wf.get("name", "")})

        # Execute workflow steps
        for i, step in enumerate(wf.get("steps", []), start=1):
            agent_kind = (step.get("agent") or "research").lower()
            user_instr = render_with_ctx(step.get("instructions", "") or "")

            agent = map_agent(agent_kind)
            p = prompts.get(agent_kind, {})
            description = (
                ((user_instr + "\n\n") if user_instr else "") + 
                p.get("description", "Produce a concise, useful output.")
            )
            expected = p.get("expected", "Produce a concise, useful output.")

            await append_log(run_id, "step:start", {
                "index": i,
                "agent": agent_kind,
                "instructions": (user_instr or "")[:240]
            })

            prev_context = "\n\n".join([o.get("text", "") for o in outputs[-2:]])
            
            # Handle research step with website pre-loading
            if agent_kind == "research":
                website = inputs.get("website", "").strip()
                pre_context = prev_context
                
                if website:
                    await append_log(run_id, "fetching_website", {
                        "index": i,
                        "url": website,
                        "reason": "Using provided website as primary source"
                    })
                    
                    from .runtime_agents import clean_url
                    try:
                        # Fetch with timeout
                        website_content = await asyncio.wait_for(
                            asyncio.to_thread(clean_url._run, website),
                            timeout=20.0
                        )
                        
                        if website_content and "Download failed" not in website_content:
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
                    except asyncio.TimeoutError:
                        await append_log(run_id, "website_fetch_failed", {
                            "index": i,
                            "error": "Timeout after 20s"
                        })
                    except Exception as e:
                        await append_log(run_id, "website_fetch_failed", {
                            "index": i,
                            "error": str(e)
                        })
                
                # Run research with retry and circuit breaker
                try:
                    text_out = await _run_agent_with_retry(
                        agent, description, expected, pre_context
                    )
                except RateLimitError as e:
                    await append_log(run_id, "rate_limit_hit", {
                        "index": i,
                        "error": str(e),
                        "recommendation": "Please try again in a few minutes"
                    })
                    raise
                    
            else:
                # Non-research tasks
                try:
                    text_out = await _run_agent_with_retry(
                        agent, description, expected, prev_context
                    )
                except RateLimitError as e:
                    await append_log(run_id, "rate_limit_hit", {
                        "index": i,
                        "error": str(e)
                    })
                    raise

            # Log output
            preview = text_out[:600]
            data = {"index": i, "agent": agent_kind, "preview": preview}
            if agent_kind == "outreach":
                data["full"] = text_out
            await append_log(run_id, "step:output", data)

            outputs.append({"index": i, "agent": agent_kind, "text": text_out})
            await append_log(run_id, "step:end", {"index": i})

            # Quality gate for research
            if agent_kind == "research":
                from .runtime_agents import score_research_quality
                
                quality_score = score_research_quality(text_out)
                
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
                
                if not quality_score["passed"]:
                    reason = f"Research confidence too low ({quality_score['confidence']}%)"
                    detail_parts = []
                    
                    if quality_score["total_credible"] == 0:
                        detail_parts.append("No credible sources found")
                    else:
                        detail_parts.append(
                            f"Found {quality_score['total_credible']} credible source(s), "
                            "need 2+ high-quality"
                        )
                    
                    if quality_score["total_urls"] > 0:
                        detail_parts.append(f"Checked {quality_score['total_urls']} URLs total")
                    
                    detail = " • ".join(detail_parts)
                    
                    await append_log(run_id, "finished", {
                        "status": "stopped",
                        "reason": reason,
                        "detail": detail,
                        "recommendation": (
                            "Manual research recommended - try alternative sources "
                            "or verify company name"
                        )
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
            
            # Qualification gate
            if agent_kind == "qualify":
                try:
                    q = json.loads(text_out)
                except Exception:
                    q = {
                        "score": 0,
                        "decision": "no",
                        "reasons": ["Invalid qualification format"]
                    }
                
                matches = q.get("criterion_match") or {}
                reasons = q.get("reasons") or []
                score = int(q.get("score", 0))
                positives = sum(bool(v) for v in matches.values())
                
                if positives < 2:
                    score = min(score, 60)
                    q["score"] = score
                    q["decision"] = "maybe" if score >= 50 else "no"
                    if "Low evidence count" not in " ".join(reasons):
                        q["reasons"].append(
                            f"Only {positives} ICP criterion clearly matched (need 2+)"
                        )
                
                if positives >= 4 and score >= 80:
                    q["confidence"] = "high"
                elif positives >= 3 and score >= 65:
                    q["confidence"] = "medium"
                elif positives >= 2 and score >= 50:
                    q["confidence"] = "low"
                else:
                    q["confidence"] = "insufficient"
                
                text_out = json.dumps(q, indent=2)
                
                await append_log(run_id, "qualify:assessed", {
                    "index": i,
                    "score": q["score"],
                    "decision": q["decision"],
                    "confidence": q.get("confidence", "unknown"),
                    "criteria_matched": positives,
                    "total_criteria": len(matches)
                })
                
                if q["decision"] == "no" and q["score"] < 40:
                    await append_log(run_id, "finished", {
                        "status": "stopped",
                        "reason": f"Lead disqualified (score: {q['score']}/100)",
                        "detail": " • ".join(q["reasons"][:3]),
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

        # All steps completed successfully
        await append_log(run_id, "finished", {"status": "success"})
        await db.workflow_runs.update_one(
            {"_id": ObjectId(run_id)},
            {"$set": {
                "status": "success",
                "finished_at": datetime.now(timezone.utc),
                "output": {"steps": outputs}
            }}
        )

    except RateLimitError as e:
        # Rate limit errors are already logged, just update status
        logger.warning(f"Workflow {run_id} hit rate limit: {e}")
        await db.workflow_runs.update_one(
            {"_id": ObjectId(run_id)},
            {"$set": {
                "status": "rate_limited",
                "finished_at": datetime.now(timezone.utc),
                "error": "OpenAI API rate limit exceeded. Please try again in a few minutes."
            }}
        )
        
    except Exception as e:
        logger.exception(f"Workflow {run_id} failed with unexpected error")
        await append_log(run_id, "error", {"message": str(e)})
        await db.workflow_runs.update_one(
            {"_id": ObjectId(run_id)},
            {"$set": {
                "status": "error",
                "finished_at": datetime.now(timezone.utc),
                "error": str(e)
            }}
        )
