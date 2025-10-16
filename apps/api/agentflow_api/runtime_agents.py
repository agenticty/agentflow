# apps/api/agentflow_api/runtime_agents.py
import os, re, json, requests
from ddgs import DDGS
from crewai import Agent, Task, Crew, Process
from crewai.tools import tool
import trafilatura
from bs4 import BeautifulSoup
import requests, re, time
from .agents.tools import USER_AGENT
from functools import lru_cache  
session = requests.Session()  

def bing_html_search(query: str, max_results: int = 12) -> list[dict]:
    """Key-free fallback search that scrapes Bing HTML."""
    url = "https://www.bing.com/search"
    params = {"q": query, "count": max_results}
    headers = {"User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "  # realistic UA
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")}
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        resp.raise_for_status()                  # raises HTTPError on 4xx/5xx :contentReference[oaicite:4]{index=4}
    except requests.RequestException:
        return []                                # network or HTTP failure → empty

    soup = BeautifulSoup(resp.text, "html.parser")
    hits = []
    for li in soup.select("li.b_algo")[:max_results]:
        a = li.find("h2").find("a", href=True) if li.find("h2") else None
        if not a: 
            continue
        title = a.get_text(" ", strip=True)
        url   = a["href"]
        snippet_node = li.find("p")
        snippet = snippet_node.get_text(" ", strip=True) if snippet_node else ""
        hits.append({"title": title, "snippet": snippet, "url": url})
    return hits

@tool("web_search")
def web_search(query: str) -> str:
    """
    Search DuckDuckGo (DDGS) for recent information.
    
    Args:
        query: Search query string (e.g. "OpenAI news 2025")
    
    Returns:
        JSON string with search results
    """
    import time, json
    prefer = ("openai.com","salesforce.com","reuters.com","bloomberg.com",
              "wsj.com","ft.com","bbc.co.uk","apnews.com","nvidia.com")

    # ---- DDGS primary search (with retries from Step 1) ----
    hits = []
    MAX_TRIES = 3
    for attempt in range(1, MAX_TRIES + 1):
        with DDGS() as d:
            hits = list(d.text(query, max_results=12, safesearch="moderate"))
        if hits: break
        time.sleep(1.2 * attempt)

    # ---- Fallback to Bing HTML scraper ----
    if not hits:
        hits = bing_html_search(query, max_results=12)

    # ---- Rank & trim ----
    def score(h):
        url = (h.get("href") or h.get("url") or "").lower()
        return 100 if any(p in url for p in prefer) else 0
    hits = sorted(hits, key=score, reverse=True)

    items = [{"title": h.get("title",""),
              "snippet": h.get("body") or h.get("snippet") or h.get("excerpt",""),
              "url": h.get("href") or h.get("url","")}
             for h in hits if (h.get("href") or h.get("url"))]

    return json.dumps(items[:8], ensure_ascii=False)




@tool
def clean_url(url: str) -> str:
    """
    Fetch `url` and return the main readable text.
    Raises ValueError if the download fails or no article text is found.
    """
    raw = trafilatura.fetch_url(url)           # download + encoding handling
    if not raw:
        raise ValueError("Download failed")

    text = trafilatura.extract(raw, output_format="txt")  # plain text
    if not text:
        raise ValueError("No extractable text")
    return text
    
@tool    
def backup_search(company: str) -> str:
    """
    Backup search using direct website fetch when DuckDuckGo fails.
    Returns basic company info from their official site.
    """
    try:
        # Common company website patterns
        domains_to_try = [
            f"https://www.{company.lower().replace(' ', '')}.com",
            f"https://{company.lower().replace(' ', '')}.com",
            f"https://www.{company.lower().replace(' ', '')}.ai",
        ]
        
        for domain in domains_to_try:
            try:
                headers = {"User-Agent": USER_AGENT}
                resp = requests.get(domain, timeout=10, headers=headers, allow_redirects=True)
                
                if resp.status_code == 200:
                    html = resp.text
                    
                    # Extract title
                    title_match = re.search(r"(?is)<title>(.*?)</title>", html)
                    title = title_match.group(1).strip() if title_match else company
                    
                    # Extract meta description
                    desc_match = re.search(r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']', html, re.I)
                    description = desc_match.group(1).strip() if desc_match else ""
                    
                    # Clean content
                    clean = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
                    clean = re.sub(r"(?s)<[^>]+>", " ", clean)
                    clean = re.sub(r"\s+", " ", clean).strip()
                    
                    result = {
                        "title": title,
                        "snippet": description or clean[:200],
                        "url": domain,
                        "source": "official_website"
                    }
                    
                    return json.dumps([result], ensure_ascii=False)
            except:
                continue
        
        return json.dumps({"error": "Could not find company website"}, ensure_ascii=False)
    
    except Exception as e:
        return json.dumps({"error": f"Backup search failed: {e}"}, ensure_ascii=False)

def make_researcher(*, include_backup: bool = True) -> Agent:
    """Return a Research Analyst Agent; omit backup_search if not needed."""
    from datetime import datetime
    
    tools_list = [web_search, clean_url]
    if include_backup:
        tools_list.append(backup_search)

    current_date = datetime.now().strftime("%B %d, %Y")  # e.g., "October 16, 2025"
    
    return Agent(
        role="Research Analyst",
        goal=(
            f"Find factual company information using provided website and news "
            f"sources. Today is {current_date}. Skip blocked URLs immediately; cite every claim."
        ),
        backstory=(
            f"You favour primary sources and recent information (current date: {current_date}). "
            "If a URL returns 401/403 you skip it. "
            "Redundant downloads are wasteful—avoid them."
        ),
        tools=tools_list,
        verbose=True,
        allow_delegation=False,
        max_iter=20,
        memory=False,
    )


def make_qualifier():
    return Agent(role="Qualifier", goal="Evaluate fit using provided research and simple criteria.",
                 backstory="Scores leads and explains why.", tools=[], verbose=False, allow_delegation=False)

def make_outreach():
    return Agent(role="Outreach Writer", goal="Draft a concise, personalized outreach based on context.",
                 backstory="B2B writer—clear, specific, no fluff.", tools=[], verbose=False, allow_delegation=False)

def map_agent(kind: str, **kwargs) -> Agent:
    k = (kind or "").lower()
    if k == "research": return make_researcher(**kwargs)
    if k == "qualify":  return make_qualifier()
    if k == "outreach": return make_outreach()
    return make_researcher()

def run_single_task(agent: Agent, description: str, expected_output: str, context_text: str = "") -> str:
    desc = f"{description}\n\nCONTEXT (if any):\n{context_text}" if context_text else description
    task = Task(description=desc, expected_output=expected_output, agent=agent)
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)
    result = crew.kickoff()
    return str(result)

def score_research_quality(text_out: str) -> dict:
    """
    Score research output quality based on source credibility.
    Returns confidence score and metadata.
    """
    import re
    
    # Tier 1: Premium news, business, and financial sources (highest credibility)
    tier1_domains = [
        # Financial News (Premium)
        "reuters.com", "bloomberg.com", "wsj.com", "ft.com", "economist.com",
        "finance.yahoo.com", "money.cnn.com", "marketwatch.com", "cnbc.com",
        "barrons.com", "investing.com", "morningstar.com",
        
        # General News (Established)
        "apnews.com", "bbc.co.uk", "bbc.com", "nytimes.com", "washingtonpost.com",
        "theguardian.com", "latimes.com", "usatoday.com",
        
        # Business Publications
        "fortune.com", "inc.com", "fastcompany.com", "businessweek.com",
        "hbr.org", "mckinsey.com", "bcg.com", "bain.com",
        
        # Tech Business News
        "axios.com", "theinformation.com", "protocol.com"
    ]
    
    # Tier 2: Tech/industry sources, trade publications, and reputable blogs
    tier2_domains = [
        # Tech News (Major)
        "techcrunch.com", "theverge.com", "wired.com", "arstechnica.com",
        "venturebeat.com", "engadget.com", "gizmodo.com", "cnet.com",
        "zdnet.com", "techradar.com", "digitaltrends.com",
        
        # Business/Tech Hybrid
        "forbes.com", "businessinsider.com", "entrepreneur.com",
        
        # Developer & Tech Community
        "medium.com", "dev.to", "hackernoon.com", "infoq.com",
        "techrepublic.com", "computerworld.com", "informationweek.com",
        
        # Industry Specific
        "adweek.com", "marketingdive.com", "retaildive.com", "industrydive.com",
        "mobihealthnews.com", "fiercehealthcare.com", "healthcaredive.com",
        
        # SaaS & Startup Ecosystem
        "saastr.com", "saasmetrics.co", "chargebee.com/blog", "stripe.com/blog",
        "productboard.com/blog", "intercom.com/blog", "segment.com/blog",
        
        # Research & Analysis
        "gartner.com", "forrester.com", "idc.com", "451research.com",
        "cbinsights.com", "pitchbook.com", "crunchbase.com"
    ]
    
    # Tier 3: Official company sources and verified press releases
    tier3_patterns = [
        # Major Tech Companies
        r"nvidia\.com", r"openai\.com", r"anthropic\.com", r"microsoft\.com",
        r"apple\.com", r"google\.com", r"amazon\.com", r"meta\.com",
        r"salesforce\.com", r"oracle\.com", r"ibm\.com", r"adobe\.com",
        r"sap\.com", r"servicenow\.com", r"workday\.com", r"zoom\.us",
        
        # Cloud & Infrastructure
        r"aws\.amazon\.com", r"azure\.microsoft\.com", r"cloud\.google\.com",
        r"digitalocean\.com", r"cloudflare\.com", r"fastly\.com",
        
        # Enterprise Software
        r"hubspot\.com", r"zendesk\.com", r"atlassian\.com", r"slack\.com",
        r"notion\.so", r"asana\.com", r"monday\.com", r"clickup\.com",
        r"airtable\.com", r"smartsheet\.com",
        
        # Common corporate page patterns
        r"/news", r"/newsroom", r"/press", r"/press-release", r"/blog",
        r"/about", r"/company", r"/investors", r"/media",
        
        # Press Release Wires
        r"businesswire\.com", r"prnewswire\.com", r"globenewswire\.com",
        r"accesswire\.com", r"marketwired\.com"
    ]
    
    text_lower = text_out.lower()
    
    # Count credible sources by tier
    tier1_count = sum(1 for d in tier1_domains if d in text_lower)
    tier2_count = sum(1 for d in tier2_domains if d in text_lower)
    tier3_count = sum(1 for pattern in tier3_patterns if re.search(pattern, text_lower))
    
    total_credible = tier1_count + tier2_count + tier3_count
    
    # Extract all URLs
    urls = re.findall(r'https?://[^\s\)\]]+', text_out)
    total_urls = len(urls)
    
    # Calculate confidence score (UPDATED THRESHOLDS)
    if tier1_count >= 2:
        confidence = 95
        quality = "high"
    elif tier1_count >= 1 and tier2_count >= 1:
        confidence = 90
        quality = "high"
    elif tier1_count >= 1 and tier3_count >= 1:
        confidence = 85
        quality = "high"
    elif tier1_count >= 1:
        confidence = 80
        quality = "good"
    elif tier2_count >= 2:
        confidence = 75
        quality = "good"
    elif tier2_count >= 1 and tier3_count >= 1:
        confidence = 70
        quality = "good"
    elif tier3_count >= 2:  # Multiple official sources
        confidence = 65
        quality = "good"
    elif total_credible >= 1:
        confidence = 55
        quality = "medium"
    else:
        confidence = 25
        quality = "insufficient"
    
    return {
        "confidence": confidence,
        "quality": quality,
        "tier1_sources": tier1_count,
        "tier2_sources": tier2_count,
        "tier3_sources": tier3_count,
        "total_credible": total_credible,
        "total_urls": total_urls,
        "passed": confidence >= 55
    }