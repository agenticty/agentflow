# apps/api/agents/tools.py
import json
import re
import requests
from typing import List, Dict, Any
from ddgs import DDGS
from crewai.tools import tool

USER_AGENT = "Mozilla/5.0 (AgentFlow/0.1; +https://example.local)"

@tool
def web_search(query: str) -> str:
    """Search DuckDuckGo. Input is a search query string. Returns JSON list of {title, snippet, url}."""
    try:
        q = (query or "").strip()
        if not q:
            return json.dumps({"error": "empty query"}, ensure_ascii=False)

        with DDGS() as d:
            hits = list(d.text(q, max_results=8, region="wt-wt"))

        if not hits:
            with DDGS() as d:
                hits = list(d.news(q, max_results=8, region="wt-wt"))

        items: List[Dict[str, Any]] = []
        for h in hits:
            url = h.get("href") or h.get("url") or ""
            if not url:
                continue
            items.append({
                "title": h.get("title", ""),
                "snippet": h.get("body", h.get("excerpt", "")),
                "url": url,
            })
        return json.dumps(items, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"search failed: {e}"}, ensure_ascii=False)

@tool
def fetch_url(url: str) -> str:
    """Fetch a URL and return lightly cleaned text (title + first ~1500 chars)."""
    try:
        headers = {"User-Agent": USER_AGENT}
        resp = requests.get(url, timeout=15, headers=headers, allow_redirects=True)
        resp.raise_for_status()
        html = resp.text
        title = re.search(r"(?is)<title>(.*?)</title>", html)
        title = title.group(1).strip() if title else url
        clean = re.sub(r"(?is)<(script|style).*?>.*?</\\1>", " ", html)
        clean = re.sub(r"(?s)<[^>]+>", " ", clean)
        clean = re.sub(r"\s+", " ", clean).strip()
        return f"TITLE: {title}\nURL: {url}\nCONTENT: {clean[:1500]}"
    except Exception as e:
        return f"ERROR fetching {url}: {e}"
