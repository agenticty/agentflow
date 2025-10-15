# apps/api/agentflow_api/runtime_agents.py
import os, re, json, requests
from duckduckgo_search import DDGS
from crewai import Agent, Task, Crew, Process
from crewai.tools import tool

@tool
def web_search(query: str) -> str:
    """Search DuckDuckGo for the past 12 months; return credible hits first (official site, tier-1)."""
    import time
    one_year_ago = time.time() - 365*24*3600
    with DDGS() as d:
        hits = list(d.text(query, max_results=12, region="wt-wt"))
    # rank: official domains and tier-1 first
    prefer = ("openai.com","salesforce.com","reuters.com","bloomberg.com","wsj.com","ft.com","bbc.co.uk","apnews.com","nvidia.com")
    def score(h):
        u = (h.get("href") or h.get("url") or "").lower()
        s = 100 if any(p in u for p in prefer) else 0
        # ddgs returns no date reliably; keep simple domain bias
        return s
    hits = sorted(hits, key=score, reverse=True)
    items = [{"title": h.get("title",""), "snippet": h.get("body", h.get("excerpt","")),
              "url": h.get("href", h.get("url",""))} for h in hits if h.get("href") or h.get("url")]
    return json.dumps(items[:8], ensure_ascii=False)


@tool
def fetch_url(url: str) -> str:
    """Fetch a URL and return lightly cleaned text (title + first ~1500 chars)."""
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        html = r.text
        title = re.search(r"(?is)<title>(.*?)</title>", html)
        title = title.group(1).strip() if title else url
        clean = re.sub(r"(?is)<(script|style).*?>.*?</\\1>", " ", html)
        clean = re.sub(r"(?s)<[^>]+>", " ", clean)
        clean = re.sub(r"\s+", " ", clean).strip()
        return f"TITLE: {title}\nURL: {url}\nCONTENT: {clean[:1500]}"
    except Exception as e:
        return f"ERROR fetching {url}: {e}"

def make_researcher():
    return Agent(role="Researcher", goal="Find trustworthy, recent info and summarize with sources.",
                 backstory="Concise analyst with citations.", tools=[web_search, fetch_url],
                 verbose=False, allow_delegation=False)

def make_qualifier():
    return Agent(role="Qualifier", goal="Evaluate fit using provided research and simple criteria.",
                 backstory="Scores leads and explains why.", tools=[], verbose=False, allow_delegation=False)

def make_outreach():
    return Agent(role="Outreach Writer", goal="Draft a concise, personalized outreach based on context.",
                 backstory="B2B writer—clear, specific, no fluff.", tools=[], verbose=False, allow_delegation=False)

def map_agent(kind: str) -> Agent:
    k = (kind or "").lower()
    if k == "research": return make_researcher()
    if k == "qualify":  return make_qualifier()
    if k == "outreach": return make_outreach()
    return make_researcher()

def run_single_task(agent: Agent, description: str, expected_output: str, context_text: str = "") -> str:
    desc = f"{description}\n\nCONTEXT (if any):\n{context_text}" if context_text else description
    task = Task(description=desc, expected_output=expected_output, agent=agent)
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)
    result = crew.kickoff()
    return str(result)
