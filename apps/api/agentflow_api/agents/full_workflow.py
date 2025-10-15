# apps/api/agents/full_workflow.py
import os
from typing import Any, Dict, Optional

from dotenv import load_dotenv

from .research_crew import run_research_crew, AgentRunError as ResearchError
from .qualify_crew import run_qualify_crew, AgentRunError as QualifyError
from .outreach_crew import run_outreach_crew, AgentRunError as OutreachError

load_dotenv()

class AgentRunError(Exception):
    """Raised when the full workflow cannot complete."""

def run_full_workflow(company: str, persona: str = "RevOps Lead") -> Dict[str, Any]:
    """
    Orchestrates:
      1) Research (topic=company, audience fixed)
      2) Qualify (JSON decision)
      3) Outreach (only if qualified; uses research as context)

    Returns a dict:
      {
        "status": "success",
        "research": "<markdown or 'I can't answer that.'>",
        "decision": { ... } | null,
        "outreach": { "subject": "...", "body": "..." } | null
      }
    Raises:
      AgentRunError (400-level in API) for expected issues (config/inputs).
      Other exceptions bubble as 500 in the API layer.
    """
    if not os.getenv("OPENAI_API_KEY"):
        raise AgentRunError("Missing OPENAI_API_KEY. Set it in your environment or .env.")
    company = (company or "").strip()
    if len(company) < 2:
        raise AgentRunError("Company name is too short.")

    # 1) Research — we’ll reuse the topic research crew, passing the company name as the topic.
    #     Audience is fixed to something sensible for the brief.
    try:
        research_md = run_research_crew(topic=company, audience="Sales/RevOps leadership")
    except ResearchError as e:
        # Turn into a structured response that the API will map to 400
        raise AgentRunError(f"Research failed: {e}")

    # If research is inconclusive, stop early
    if research_md.strip() == "I can't answer that.":
        return {
            "status": "success",
            "research": research_md,
            "decision": {
                "qualified": False,
                "fit_score": 0,
                "reasons": ["insufficient verified research"],
                "suggested_persona": "",
                "key_hooks": []
            },
            "outreach": None
        }

    # 2) Qualify — reuse your existing qualify crew (per Day 9).
    try:
        decision = run_qualify_crew(company)
    except QualifyError as e:
        raise AgentRunError(f"Qualification failed: {e}")

    # 3) Outreach — only if qualified
    outreach: Optional[Dict[str, str]] = None
    if bool(decision.get("qualified")):
        persona_arg = (decision.get("suggested_persona") or persona or "RevOps Lead").strip()
        hooks = decision.get("key_hooks") or []
        try:
            outreach = run_outreach_crew(
                company=company,
                persona=persona_arg,
                hooks=hooks,
                context=research_md,   # use research as grounding; no extra web calls
            )
        except OutreachError as e:
            # Outreach isn’t critical; return decision + research even if email fails
            outreach = None

    return {
        "status": "success",
        "research": research_md,
        "decision": decision,
        "outreach": outreach
    }
