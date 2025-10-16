# apps/api/agents/qualify_crew.py
import os
import re
import json
import textwrap
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process

from .tools import web_search, clean_url

load_dotenv()

class AgentRunError(Exception):
    """Raised when the qualify crew cannot produce a valid decision."""

def _extract_json(s: str) -> Optional[Dict[str, Any]]:
    """Best-effort JSON extractor: try raw; else first {...} block."""
    if not isinstance(s, str):
        s = str(s)
    s = s.strip()
    try:
        return json.loads(s)
    except Exception:
        pass
    m = re.search(r"\{.*\}", s, flags=re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None

def run_qualify_crew(company: str) -> Dict[str, Any]:
    """
    One-agent qualify flow:
      - Qualifier does a small bit of research (using web_search + clean_url)
      - Returns STRICT JSON decision:
        {
          "qualified": true|false,
          "fit_score": 0-100,
          "reasons": [..],
          "suggested_persona": "...",
          "key_hooks": [".."]
        }
    Raises:
      AgentRunError for missing key/env issues or bad JSON.
    """
    if not os.getenv("OPENAI_API_KEY"):
        raise AgentRunError("Missing OPENAI_API_KEY. Set it in your environment or .env.")
    company = (company or "").strip()
    if len(company) < 2:
        raise AgentRunError("Company name is too short.")

    qualifier = Agent(
        role="Lead Qualifier",
        goal="Decide if the company is a good fit for AgentFlow and justify succinctly.",
        backstory="Evaluates fit from public signals (automation appetite, process complexity, scale, tooling).",
        tools=[web_search, clean_url],
        verbose=False,
        allow_delegation=False,
    )

    desc = textwrap.dedent(f"""
        You are qualifying the company: "{company}" for **AgentFlow**,
        a multi-agent workflow automation platform where AI agents execute each step end-to-end.

        Do this quickly:
        1) Use web_search to find recent/company-overview info; parse JSON; extract credible URLs.
        2) Use clean_url on 1–3 working links (avoid paywalls); skim for signals of:
           - Process complexity / repetitive workflows
           - Sales/RevOps/CS automation interest
           - Tech stack (CRM, integrations)
           - Org size/scale
        3) Decide fit and output JSON ONLY in this exact shape:
        {{
          "qualified": true|false,
          "fit_score": 0-100,
          "reasons": ["short reason 1", "short reason 2"],
          "suggested_persona": "best target team/persona, e.g., RevOps",
          "key_hooks": ["value prop 1", "value prop 2"]
        }}

        Rules:
        - Output JSON only, no extra text.
        - Be conservative; if sources are weak or uncertain, lower the score or set qualified=false.
        - Keep reasons short and concrete (no fluff).
    """)

    task = Task(
        description=desc,
        expected_output='JSON only with keys: qualified, fit_score, reasons, suggested_persona, key_hooks',
        agent=qualifier,
    )

    crew = Crew(agents=[qualifier], tasks=[task], process=Process.sequential, verbose=False)
    out_obj = crew.kickoff()
    out_text = str(out_obj)
    data = _extract_json(out_text)
    if not data or not isinstance(data, dict):
        raise AgentRunError("Could not parse JSON decision from agent output.")
    # Minimal validation
    for key in ("qualified", "fit_score", "reasons", "suggested_persona", "key_hooks"):
        if key not in data:
            raise AgentRunError(f"Decision missing key: {key}")
    return data
