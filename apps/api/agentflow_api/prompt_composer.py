import json
from typing import Dict, Any
from datetime import datetime

def _j(x: Any) -> str:
    s = json.dumps(x, ensure_ascii=False, indent=2)
    # Remove potential prompt injection patterns
    s = s.replace("IGNORE PREVIOUS", "[FILTERED]")
    s = s.replace("DISREGARD", "[FILTERED]")
    return s

def compose_prompts(org: Dict[str, Any], inputs: Dict[str, Any]):
    """
    Generate task prompts from org profile and workflow run inputs.
    
    Args:
        org: Organization profile from MongoDB
        inputs: User-provided inputs like {"company": "OpenAI", "lead_email": "..."}
    """

    org = {k:v for k,v in (org or {}).items() if k != "_id"}

    company = inputs.get("company","").strip()
    website = inputs.get("website","").strip()
    email = inputs.get("lead_email","").strip()

    # Validation
    if not company:
        raise ValueError("Missing required input: company")
    if not email:
        # Default to generic email if not provided
        domain = website.replace("https://","").replace("http://","").split("/")[0] if website else f"{company.lower().replace(' ','')}.com"
        email = f"contact@{domain}"


    current_date = datetime.now().strftime("%B %d, %Y")
    current_year = datetime.now().year


    research = {
        "expected": (
            "3–5 factual bullets with [#] citations and a Sources list. "
            "If company website was provided in context above, USE IT as source [1]. "
            "Add 1-2 news sources if available."
        ),
        "description": (
            f"Research {company}.\n\n"
            
            f"CURRENT DATE: {current_date}\n"
            f"When searching for news, use '{current_year}' or 'recent' in your queries.\n\n"
            
            "STRATEGY:\n"
            "1. Check if company website content is provided in the context above\n"
            "2. If YES: Use that as your PRIMARY source [1] and summarize it\n"
            "3. Call web_search for recent news (use current year in query)\n"  # ← Updated
            "4. Try to clean_url on 1-2 accessible URLs from search\n"
            "5. If URLs return 403/401 errors, SKIP them immediately - don't retry\n\n"
            
            "OUTPUT FORMAT:\n"
            "- Company overview: [from website or search] [1]\n"
            "- Recent activity 1: [specific fact if found] [2]\n"
            "- Recent activity 2: [specific fact if found] [3]\n\n"
            "Sources:\n"
            f"1. {website or '(company website)'}\n"
            "2. [news URL if accessible]\n"
            "3. [news URL if accessible]\n\n"
            
            "CRITICAL RULES:\n"
            "- If context already has website content, USE IT immediately as [1]\n"
            "- Don't retry URLs that return 403/401/ERROR\n"
            "- If only company website is accessible, that's OK - use it\n"
            "- Better to have 1 good source than waste time on blocked URLs\n"
            "- Only say 'I can't answer that.' if NO sources work at all"
        )
    }

    qualify = {
      "expected": (
        "JSON only: {\"score\":0-100,\"decision\":\"yes\"|\"no\"|\"maybe\",\"reasons\":[string],"
        "\"criterion_match\":{...}}. If evidence is insufficient, reply exactly: \"I can't answer that.\""
      ),
      "description": (
        "You evaluate fit strictly against the ICP below. Only claim matches if explicitly supported by research.\n\n"
        f"ICP:\n{_j(org.get('icp', {}))}\n"
        f"Disqualifiers: {_j(org.get('disqualifiers', []))}\n"
        "Return JSON only."
      ),
    }

    tone = org.get("tone") or {}
    if not isinstance(tone, dict):
        tone = {}
    # Add defaults
    tone.setdefault("style", "friendly")
    tone.setdefault("length", "short")

    contact_name = inputs.get("contact_name", "").strip()
    greeting = f"Hi {contact_name}" if contact_name else "Hi"


    outreach = {
        "expected": (
            "Start with 'Subject: ...' then blank line. "
            "Email body: 60-90 words MAX (SHORT). "
            "Include ONE specific fact from research. "
            "End with ONE clear CTA question. "
            "If you cannot reference a concrete fact, reply exactly: \"I can't answer that.\""
        ),
        "description": (
            f"Write a SHORT SDR cold email to {email} to book a sales call.\n\n"
            
            "CONTEXT:\n"
            f"Your company: {org.get('name','')} — {org.get('product_one_liner','')}\n"
            f"Value props: {_j(org.get('value_props', []))}\n"
            f"Your goal: Book a 15-20 minute discovery call\n\n"
            
            "SDR EMAIL RULES (STRICTLY FOLLOW):\n"
            "1. OPENING: Start with ONE specific insight from research (not generic praise)\n"
            "2. CONNECTION: In 1-2 sentences, connect that insight to a pain point your product solves\n"
            "3. CTA: End with ONE clear question to book a call (e.g., 'Worth a quick call?', 'Open to a 15-min conversation?')\n"
            "4. LENGTH: 60-90 words MAXIMUM (be punchy - they get 50+ emails/day)\n"
            "5. TONE: Direct, helpful, consultative (NOT salesy, NOT partnership-focused)\n\n"
            
            "FORBIDDEN PHRASES (never use these):\n"
            "❌ 'I hope this finds you well'\n"
            "❌ 'enhance your initiatives' or 'strategic partnership'\n"
            "❌ 'reaching out to discuss collaboration'\n"
            "❌ 'thought leadership' or 'synergies'\n"
            "❌ Any greeting longer than 'Hi [Name],' or 'Hey [Name],'\n\n"
            
            "GOOD SDR EMAIL STRUCTURE:\n"
            "Subject: [Specific + relevant to their situation]\n\n"
            "Hi [Name],\n\n"
            "Saw [specific thing from research]. [Connect to pain point]. [Your solution's value prop in one sentence].\n\n"
            "Worth a 15-min call [specific day/timeframe]?\n\n"
            "Best,\n[Name]\n[Title]\n"
            f"{org.get('name','')}\n"
            f"{org.get('outreach_footer','')}\n\n"
            
            "EXAMPLE (follow this style):\n"
            "Subject: Quick question about your AMD deployment\n\n"
            "Hi Sam,\n\n"
            "Noticed OpenAI just deployed 6GW of AMD GPUs. Companies scaling AI infrastructure this fast often hit bottlenecks managing customer data across engineering and sales teams. Our CRM helps AI companies centralize that without slowing down velocity.\n\n"
            "Worth a 15-min call Thursday or Friday?\n\n"
            "Best,\nAlex\nEnterprise Sales\nSalesforce\n\n"
            
            "Now write the actual email using the research and qualifier context below. "
            "Be specific, be brief, get the meeting."
        ),
    }

    return {"research": research, "qualify": qualify, "outreach": outreach}
