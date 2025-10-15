# apps/api/agents/outreach_crew.py
import os
import textwrap
from typing import List, Optional, Dict, Any

from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process

from .tools import web_search, fetch_url

load_dotenv()

class AgentRunError(Exception):
    """Raised when the outreach crew cannot produce a valid email."""

def _normalize_hooks(hooks: Optional[List[str]]) -> str:
    if not hooks:
        return ""
    cleaned = [h.strip() for h in hooks if h and h.strip()]
    return ", ".join(cleaned[:5])  # cap to 5 hooks for prompt brevity

def run_outreach_crew(
    company: str,
    persona: str = "RevOps Lead",
    hooks: Optional[List[str]] = None,
    context: Optional[str] = None,
) -> Dict[str, str]:
    """
    Draft a concise cold outreach email to `company`.
    - If `context` is provided, rely on it and DO NOT perform web research.
    - If `context` is empty, do a quick web check (1–2 sources) for personalization.

    Returns:
      {"subject": "...", "body": "..."}
    Raises:
      AgentRunError on missing API key, invalid inputs, or empty output.
    """
    if not os.getenv("OPENAI_API_KEY"):
        raise AgentRunError("Missing OPENAI_API_KEY. Set it in your environment or .env.")
    company = (company or "").strip()
    if len(company) < 2:
        raise AgentRunError("Company name is too short.")

    hooks_str = _normalize_hooks(hooks)

    # Writer agent. Attach tools ONLY if context is absent (so it can do a quick check).
    writer = Agent(
        role="Outreach Email Writer",
        goal="Write a short, personalized cold email pitching AgentFlow with a clear CTA.",
        backstory="You craft respectful, concise B2B emails. You reference specifics responsibly.",
        tools=[] if context else [web_search, fetch_url],
        verbose=False,
        allow_delegation=False,
    )

    # Build the task description
    base_rules = f"""
        - Subject line (one line)
        - 120–160 word body
        - Audience persona: "{persona}"
        - Explain AgentFlow in one sentence:
          "AgentFlow is a multi-agent workflow automation platform where AI agents execute each step end-to-end."
        - Use 2–3 relevant value props: {hooks_str or "faster lead handling, reduced manual ops, consistent QA, scalable outreach"}
        - Clear CTA (e.g., 20-minute demo next week)
        - Professional, human tone, no hype. No footnotes or references required.
        - Output JSON ONLY with keys: "subject" and "body".
    """

    if context:
        desc = textwrap.dedent(f"""
            Write a personalized cold email to "{company}" using ONLY the context below.

            Context:
            ---
            {context.strip()}
            ---

            Rules:
            {base_rules}

            Do NOT perform any new web research. If the context lacks specifics, keep the email generic but relevant to workflow automation.
        """)
    else:
        desc = textwrap.dedent(f"""
            Write a personalized cold email to "{company}". You MAY perform a quick web check for 1–2 facts.

            Steps (if you choose to research):
            1) Use web_search for "{company} company overview" or "news {company}".
            2) Parse JSON results; pick 1–2 credible URLs.
            3) Use fetch_url on 1–2 links. If blocked/paywalled, skip it.

            Use any discovered fact(s) sparingly—only if confident.

            Rules:
            {base_rules}

            If you found nothing reliable, keep personalization light (role/team, responsibilities) and focus on value props.
        """)

    task = Task(
        description=desc,
        expected_output='JSON only: {"subject": "...", "body": "..."}',
        agent=writer,
    )

    crew = Crew(agents=[writer], tasks=[task], process=Process.sequential, verbose=False)
    out_obj = crew.kickoff()
    out_text = str(out_obj).strip()

    # Very small JSON extraction (email body shouldn't be huge)
    import json, re
    try:
        email = json.loads(out_text)
        subject = (email.get("subject") or "").strip()
        body = (email.get("body") or "").strip()
    except Exception:
        # try to snip first { ... }
        m = re.search(r"\{.*\}", out_text, flags=re.DOTALL)
        if not m:
            raise AgentRunError("Could not parse outreach JSON from agent output.")
        email = json.loads(m.group(0))
        subject = (email.get("subject") or "").strip()
        body = (email.get("body") or "").strip()

    if not subject or not body:
        raise AgentRunError("Outreach email is empty or missing subject/body.")
    return {"subject": subject, "body": body}
