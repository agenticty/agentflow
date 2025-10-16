import json
import re
import time
import requests
from typing import List, Dict, Any
from ddgs import DDGS
from crewai.tools import tool
import trafilatura

USER_AGENT = "Mozilla/5.0 (AgentFlow/1.0; +https://agentflow.app)"

@tool
def web_search(query: str) -> str:
    """
    Search DuckDuckGo with quality ranking.
    Prioritizes credible news/tech sources.
    Returns JSON list of {title, snippet, url, quality_tier}.
    """
    try:
        q = (query or "").strip()
        if not q:
            return json.dumps({"error": "empty query"}, ensure_ascii=False)
        
        # Tier 1: Premium sources (most credible)
        tier1_domains = [
            "reuters.com", "bloomberg.com", "wsj.com", "ft.com",
            "apnews.com", "bbc.co.uk", "economist.com"
        ]
        
        # Tier 2: Tech/industry sources
        tier2_domains = [
            "techcrunch.com", "theverge.com", "wired.com", "arstechnica.com",
            "venturebeat.com", "forbes.com", "businessinsider.com"
        ]
        
        # Tier 3: Company/official sources
        tier3_domains = [
            ".com/news", ".com/blog", ".com/press-release", 
            ".com/newsroom", "medium.com/@"
        ]
        
        with DDGS() as d:
            # Try news first (more recent)
            hits = list(d.news(q, max_results=10, region="wt-wt"))
            
            # Fallback to text search if no news
            if len(hits) < 3:
                text_hits = list(d.text(q, max_results=10, region="wt-wt"))
                hits.extend(text_hits)
        
        if not hits:
            return json.dumps({"error": "no results found"}, ensure_ascii=False)
        
        # Score and rank results
        def score_url(url: str) -> tuple[int, int]:
            """Return (tier, priority) - lower is better."""
            url_lower = url.lower()
            
            if any(d in url_lower for d in tier1_domains):
                return (1, 0)
            if any(d in url_lower for d in tier2_domains):
                return (2, 0)
            if any(d in url_lower for d in tier3_domains):
                return (3, 0)
            
            # Company official domains get tier 3
            if "/blog" in url_lower or "/news" in url_lower:
                return (3, 1)
            
            # Everything else is tier 4
            return (4, 0)
        
        items: List[Dict[str, Any]] = []
        for h in hits:
            url = h.get("href") or h.get("url") or ""
            if not url:
                continue
            
            tier, priority = score_url(url)
            
            items.append({
                "title": h.get("title", ""),
                "snippet": h.get("body", h.get("excerpt", "")),
                "url": url,
                "quality_tier": tier,
                "_sort_priority": priority,
            })
        
        # Sort by quality tier, then priority
        items.sort(key=lambda x: (x["quality_tier"], x["_sort_priority"]))
        
        # Remove internal sort field before returning
        for item in items:
            item.pop("_sort_priority", None)
        
        # Return top 8
        return json.dumps(items[:8], ensure_ascii=False)
    
    except Exception as e:
        return json.dumps({"error": f"search failed: {e}"}, ensure_ascii=False)


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