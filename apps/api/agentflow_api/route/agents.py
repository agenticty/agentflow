from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Literal, Any, Dict
import logging
import anyio
import time

from ..agents.research_crew import run_research_crew, AgentRunError
from ..agents.qualify_crew import run_qualify_crew, AgentRunError as QualifyError
from ..agents.outreach_crew import run_outreach_crew, AgentRunError as OutreachError
from ..agents.full_workflow import run_full_workflow, AgentRunError as FullFlowError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agents", tags=["agents"])

class ResearchRequest(BaseModel):
    topic: str = Field(..., min_length=2, max_length=300)
    audience: str = Field("Executive Team", min_length=2, max_length=120)

class ResearchResponse(BaseModel):
    result: str
    status: Literal["success", "error"]

@router.post("/research", response_model=ResearchResponse)
async def research_endpoint(payload: ResearchRequest):
    t0 = time.perf_counter()
    print("[agents] received request")
    try:
        result = await anyio.to_thread.run_sync(
            run_research_crew, payload.topic, payload.audience
        )
        t1 = time.perf_counter()
        print(f"[agents] crew finished in {t1 - t0:.2f}s")
        return ResearchResponse(result=result, status="success")
    except AgentRunError as e:
        print("[agents] AgentRunError:", e)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print("[agents] Unexpected:", e)
        raise HTTPException(status_code=500, detail="Agent execution failed")
    
class QualifyRequest(BaseModel):
    company: str = Field(..., min_length=2, max_length=200)

class QualifyResponse(BaseModel):
    status: Literal["success", "error"]
    decision: Dict[str, Any] | None = None  # the JSON decision when success

@router.post("/qualify", response_model=QualifyResponse)
async def qualify_endpoint(payload: QualifyRequest):
    """
    Qualify a single company. Runs in a worker thread so the event loop stays free.
    """
    try:
        decision = await anyio.to_thread.run_sync(run_qualify_crew, payload.company)
        return QualifyResponse(status="success", decision=decision)
    except QualifyError as e:
        logger.warning("Qualify agent error: %s", e)
        # Input/config problems -> 400
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected qualify failure")
        # Generic -> 500
        raise HTTPException(status_code=500, detail="Agent execution failed")

class OutreachRequest(BaseModel):
    company: str = Field(..., min_length=2, max_length=200)
    persona: str = Field("RevOps Lead", min_length=2, max_length=120)
    hooks: list[str] | None = None          # optional value props
    context: str | None = None              # optional research/context; if present, disables web research

class OutreachResponse(BaseModel):
    status: Literal["success", "error"]
    subject: str | None = None
    body: str | None = None

@router.post("/outreach", response_model=OutreachResponse)
async def outreach_endpoint(payload: OutreachRequest):
    """
    Draft a personalized outreach email. If 'context' is provided, writer will not research.
    """
    try:
        result = await anyio.to_thread.run_sync(
            run_outreach_crew,
            payload.company,
            payload.persona,
            payload.hooks,
            payload.context,
        )
        return OutreachResponse(status="success", subject=result["subject"], body=result["body"])
    except OutreachError as e:
        logger.warning("Outreach agent error: %s", e)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("Unexpected outreach failure")
        raise HTTPException(status_code=500, detail="Agent execution failed")
    
class FullWorkflowRequest(BaseModel):
  company: str = Field(..., min_length=2, max_length=200)
  persona: str = Field("RevOps Lead", min_length=2, max_length=120)

class FullWorkflowResponse(BaseModel):
  status: Literal["success", "error"]
  research: str | None = None
  decision: dict | None = None
  outreach: dict | None = None

@router.post("/full-workflow", response_model=FullWorkflowResponse)
async def full_workflow_endpoint(payload: FullWorkflowRequest):
  """
  Orchestrates research -> qualify -> outreach.
  Runs in a worker thread so the event loop stays responsive.
  """
  try:
    result = await anyio.to_thread.run_sync(
      run_full_workflow, payload.company, payload.persona
    )
    # result already includes "status", "research", "decision", "outreach"
    return FullWorkflowResponse(**result)
  except FullFlowError as e:
    logger.warning("Full workflow error: %s", e)
    raise HTTPException(status_code=400, detail=str(e))
  except Exception:
    logger.exception("Unexpected full-workflow failure")
    raise HTTPException(status_code=500, detail="Agent execution failed")
