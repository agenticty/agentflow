# apps/api/agents/research_crew.py
import os
import textwrap
from typing import Tuple

from crewai import Agent, Task, Crew, Process
from dotenv import load_dotenv

from .tools import web_search, fetch_url

load_dotenv()  # allow .env in dev

class AgentRunError(Exception):
    """Raised when the agent crew cannot produce a valid result."""

def run_research_crew(topic: str, audience: str) -> str:
    """
    Build and run a two-step crew:
      1) Researcher -> 3–5 bullet summary with sources
      2) Writer     -> 120–180 word brief for audience

    Returns:
      Final output string (Markdown / plain text)
    Raises:
      AgentRunError on known issues (e.g., missing API key or empty output)
    """
    # Basic guardrail for API key (CrewAI/OpenAI via LiteLLM)
    if not os.getenv("OPENAI_API_KEY"):
        raise AgentRunError("Missing OPENAI_API_KEY. Set it in your environment or .env.")

    # Agents
    researcher = Agent(
        role="Topic Researcher",
        goal="Find trustworthy, recent information and summarize it with sources.",
        backstory="Fast, factual reconnaissance with citations.",
        tools=[web_search, fetch_url],
        verbose=False,
        allow_delegation=False,
    )

    writer = Agent(
        role="Executive Brief Writer",
        goal="Transform research into a concise, actionable brief for the specified audience.",
        backstory="Writes for busy decision-makers; avoids hype and cites sources.",
        tools=[],
        verbose=False,
        allow_delegation=False,
    )

    # Tasks
    research_desc = textwrap.dedent(f"""
        Research the latest information about: "{topic}".

        Steps:
        1) Use web_search with queries like: "{topic} latest 2025", "news {topic}", "{topic} report insights".
        2) Parse the JSON result into objects with "title", "snippet", "url"; pick credible URLs.
        3) Call fetch_url on 2–4 working URLs (avoid paywalls). If a fetch returns "ERROR", try another URL.

        Output (Markdown):
        - Exactly 3–5 bullets, each 1–2 sentences, factual and current.
        - A "Sources" list with the URLs you actually used (2–5).
        - Use inline references like [#] mapped to "Sources".

        Guardrails:
        - Be factual; if uncertain, say "uncertain".
        - Only include valid, working URLs.
        - If you cannot verify at least 2 trustworthy sources, output exactly: "I can't answer that."
    """)

    write_desc = textwrap.dedent(f"""
        Using the research summary above, write a concise executive brief for:
        "{audience}".

        Requirements:
        - 120–180 words, neutral and practical.
        - Include 2–3 short bullet recommendations at the end.
        - Preserve [#] references where relevant and include a "Sources" line.
        - Do NOT perform new research; rely on the summary.
        - If the research said "I can't answer that." or included fewer than 2 sources,
          respond exactly with: "I can't answer that." and stop.
    """)

    research_task = Task(
        description=research_desc,
        expected_output="Markdown with 3–5 bullets and a 'Sources' list (URLs), or 'I can't answer that.'",
        agent=researcher,
    )

    writing_task = Task(
        description=write_desc,
        expected_output="120–180 word brief with 2–3 recommendations and sources, or 'I can't answer that.'",
        agent=writer,
        context=[research_task],
    )

    crew = Crew(
        agents=[researcher, writer],
        tasks=[research_task, writing_task],
        process=Process.sequential,
        verbose=False,
    )

    # Run and normalize to string
    result_obj = crew.kickoff()
    result_text = str(result_obj).strip()

    if not result_text:
        raise AgentRunError("Empty result from agent crew.")
    return result_text
