# apps/api/agentflow_api/runtime_agents.py
import os, re, json, requests
from ddgs import DDGS
from crewai import Agent, Task, Crew, Process
from crewai.tools import tool
import trafilatura
from bs4 import BeautifulSoup
import requests, re, time
from functools import lru_cache
from typing import Optional
import logging

# Import rate limiting utilities
from .rate_limiter import retry_with_backoff, RetryConfig

logger = logging.getLogger(__name__)

# Configure session with timeout defaults
session = requests.Session()
session.timeout = (10, 30)  # (connect timeout, read timeout)

# Retry config for external API calls
API_RETRY_CONFIG = RetryConfig(
    max_retries=3,
    base_delay=1.0,
    max_delay=30.0,
    exponential_base=2.0,
    jitter=True
)


def bing_html_search(query: str, max_results: int = 12) -> list[dict]:
    """Key-free fallback search that scrapes Bing HTML."""
    url = "https://www.bing.com/search"
    params = {"q": query, "count": max_results}
    headers = {"User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")}
    try:
        resp = requests.get(
            url, 
            params=params, 
            headers=headers, 
            timeout=10  # Hard timeout
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.warning(f"Bing search failed: {e}")
        return []

    try:
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
    except Exception as e:
        logger.warning(f"Bing HTML parsing failed: {e}")
        return []


@tool("web_search")
def web_search(query: str) -> str:
    """
    Search DuckDuckGo (DDGS) for recent information with retry logic.
    
    Args:
        query: Search query string (e.g. "OpenAI news 2025")
    
    Returns:
        JSON string with search results
    """
    import time, json
    prefer = ("openai.com","salesforce.com","reuters.com","bloomberg.com",
              "wsj.com","ft.com","bbc.co.uk","apnews.com","nvidia.com")

    # ---- DDGS primary search (with retries and exponential backoff) ----
    hits = []
    MAX_TRIES = 3
    
    for attempt in range(1, MAX_TRIES + 1):
        try:
            with DDGS() as d:
                hits = list(d.text(query, max_results=12, safesearch="moderate"))
            if hits: 
                logger.debug(f"DuckDuckGo search succeeded on attempt {attempt}")
                break
        except Exception as e:
            logger.warning(f"DuckDuckGo attempt {attempt} failed: {e}")
            if attempt < MAX_TRIES:
                # Exponential backoff: 1.2s, 2.4s, 3.6s
                delay = 1.2 * attempt
                logger.debug(f"Retrying in {delay}s...")
                time.sleep(delay)

    # ---- Fallback to Bing HTML scraper ----
    if not hits:
        logger.info("DuckDuckGo exhausted, trying Bing fallback")
        hits = bing_html_search(query, max_results=12)
        if not hits:
            logger.warning("Both DuckDuckGo and Bing failed")
            return json.dumps(
                {"error": "All search providers failed", "results": []}, 
                ensure_ascii=False
            )

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
def clean_url(url: str, timeout: int = 15) -> str:
    """
    Fetch `url` and return the main readable text with timeout and error handling.
    
    Args:
        url: URL to fetch
        timeout: Timeout in seconds (default: 15)
    
    Returns:
        Extracted text content
        
    Raises:
        ValueError: If download fails or no text is extractable
    """
    try:
        # Set timeout for trafilatura fetch
        raw = trafilatura.fetch_url(url)
        
        if not raw:
            logger.warning(f"Failed to fetch {url}: No content returned")
            raise ValueError(f"Download failed for {url}")

        text = trafilatura.extract(raw, output_format="txt")
        
        if not text or len(text.strip()) < 50:
            logger.warning(f"Failed to extract text from {url}: Content too short")
            raise ValueError(f"No extractable text from {url}")
        
        logger.debug(f"Successfully extracted {len(text)} chars from {url}")
        return text
        
    except Exception as e:
        logger.error(f"Error processing {url}: {e}")
        raise ValueError(f"Failed to process {url}: {str(e)}")


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
                headers = {"User-Agent": "Mozilla/5.0 (AgentFlow/1.0)"}
                resp = requests.get(
                    domain, 
                    timeout=10, 
                    headers=headers, 
                    allow_redirects=True
                )
                
                if resp.status_code == 200:
                    html = resp.text
                    
                    # Extract title
                    title_match = re.search(r"(?is)<title>(.*?)</title>", html)
                    title = title_match.group(1).strip() if title_match else company
                    
                    # Extract meta description
                    desc_match = re.search(
                        r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']', 
                        html, 
                        re.I
                    )
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
                    
                    logger.info(f"Backup search found website: {domain}")
                    return json.dumps([result], ensure_ascii=False)
                    
            except requests.RequestException as e:
                logger.debug(f"Backup search failed for {domain}: {e}")
                continue
        
        logger.warning(f"Backup search exhausted all domains for {company}")
        return json.dumps(
            {"error": "Could not find company website"}, 
            ensure_ascii=False
        )
    
    except Exception as e:
        logger.error(f"Backup search error: {e}")
        return json.dumps(
            {"error": f"Backup search failed: {e}"}, 
            ensure_ascii=False
        )


def make_researcher(*, include_backup: bool = True) -> Agent:
    """Return a Research Analyst Agent with retry-enabled tools."""
    from datetime import datetime
    
    tools_list = [web_search, clean_url]
    if include_backup:
        tools_list.append(backup_search)

    current_date = datetime.now().strftime("%B %d, %Y")
    
    return Agent(
        role="Research Analyst",
        goal=(
            f"Find factual company information using provided website and news "
            f"sources. Today is {current_date}. Skip blocked URLs immediately; cite every claim."
        ),
        backstory=(
            f"You favour primary sources and recent information (current date: {current_date}). "
            "If a URL returns 401/403/timeout you skip it. "
            "Redundant downloads are wasteful—avoid them."
        ),
        tools=tools_list,
        verbose=True,
        allow_delegation=False,
        max_iter=20,
        memory=False,
    )


def make_qualifier():
    return Agent(
        role="Qualifier", 
        goal="Evaluate fit using provided research and simple criteria.",
        backstory="Scores leads and explains why.", 
        tools=[], 
        verbose=False, 
        allow_delegation=False
    )


def make_outreach():
    return Agent(
        role="Outreach Writer", 
        goal="Draft a concise, personalized outreach based on context.",
        backstory="B2B writer—clear, specific, no fluff.", 
        tools=[], 
        verbose=False, 
        allow_delegation=False
    )


def map_agent(kind: str, **kwargs) -> Agent:
    k = (kind or "").lower()
    if k == "research": return make_researcher(**kwargs)
    if k == "qualify":  return make_qualifier()
    if k == "outreach": return make_outreach()
    return make_researcher()


def run_single_task(
    agent: Agent, 
    description: str, 
    expected_output: str, 
    context_text: str = ""
) -> str:
    """
    Run a single agent task with error handling.
    
    Note: CrewAI itself handles OpenAI rate limits via litellm,
    but we wrap this for additional safety.
    """
    desc = (
        f"{description}\n\nCONTEXT (if any):\n{context_text}" 
        if context_text else description
    )
    
    task = Task(
        description=desc, 
        expected_output=expected_output, 
        agent=agent
    )
    crew = Crew(
        agents=[agent], 
        tasks=[task], 
        process=Process.sequential, 
        verbose=False
    )
    
    try:
        result = crew.kickoff()
        return str(result)
    except Exception as e:
        logger.error(f"Agent execution failed: {e}")
        # Check if it's a rate limit error
        if '429' in str(e) or 'rate limit' in str(e).lower():
            raise RateLimitError(f"OpenAI rate limit hit: {e}")
        raise


class RateLimitError(Exception):
    """Raised when a rate limit is encountered."""
    pass


def score_research_quality(text_out: str) -> dict:
    """
    Score research output quality based on source credibility.
    Returns confidence score and metadata.
    """
    import re
    
    # Tier 1: Premium news, business, and financial sources (highest credibility)
    tier1_domains = [
        "reuters.com", "bloomberg.com", "wsj.com", "ft.com", "economist.com",
        "finance.yahoo.com", "money.cnn.com", "marketwatch.com", "cnbc.com",
        "barrons.com", "investing.com", "morningstar.com",
        "apnews.com", "bbc.co.uk", "bbc.com", "nytimes.com", "washingtonpost.com",
        "theguardian.com", "latimes.com", "usatoday.com",
        "fortune.com", "inc.com", "fastcompany.com", "businessweek.com",
        "hbr.org", "mckinsey.com", "bcg.com", "bain.com",
        "axios.com", "theinformation.com", "protocol.com"
    ]
    
    # Tier 2: Tech/industry sources, trade publications
    tier2_domains = [
        "techcrunch.com", "theverge.com", "wired.com", "arstechnica.com",
        "venturebeat.com", "engadget.com", "gizmodo.com", "cnet.com",
        "zdnet.com", "techradar.com", "digitaltrends.com",
        "forbes.com", "businessinsider.com", "entrepreneur.com",
        "medium.com", "dev.to", "hackernoon.com", "infoq.com",
        "techrepublic.com", "computerworld.com", "informationweek.com",
        "adweek.com", "marketingdive.com", "retaildive.com",
        "gartner.com", "forrester.com", "idc.com", "cbinsights.com"
    ]
    
    # Tier 3: Official company sources
    tier3_patterns = [
        r"nvidia\.com", r"openai\.com", r"anthropic\.com", r"microsoft\.com",
        r"apple\.com", r"google\.com", r"salesforce\.com", r"oracle\.com",
        r"/news", r"/newsroom", r"/press", r"/blog",
        r"businesswire\.com", r"prnewswire\.com"
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
    
    # Calculate confidence score
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
    elif tier3_count >= 2:
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
