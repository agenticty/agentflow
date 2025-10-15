import json
from typing import Dict, Any

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

    research = {
      "expected": "3–5 factual bullets with inline [#] and a 'Sources' list (2–5 URLs). If <2 credible sources, reply exactly: \"I can't answer that.\"",
      "description": (
        "You are a meticulous B2B researcher. Find what the company does, recent initiatives (≤12 months), "
        "buyers/teams mentioned, and signals relevant to {org_name}.\n\n"
        f"Company: {company}\nWebsite (optional): {website or '(none)'}\n"
        "Output strictly as specified. Do not guess.\n"
      ).format(org_name=org.get("name","our company"))
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
      "expected": "Start with 'Subject: ...' then blank line. 120–160 words. Include exactly one specific fact from research in brackets like [#] and one value prop. If you cannot reference a concrete fact, reply exactly: \"I can't answer that.\"",
      "description": (
        "Write a concise, specific B2B email.\n"
        f"To: {email}\n"
        f"Greeting: {greeting},\n"
        f"Organization: {org.get('name','')} — {org.get('product_one_liner','')}\n"
        f"Value props: {_j(org.get('value_props', []))}\n"
        f"Tone: {tone['style']}; Length: {tone['length']}\n"
        f"Include footer if provided: {org.get('outreach_footer','')}\n"
        "Only include concrete claims supported by the research/qualifier context."
        "\nMandatory: reference one concrete researched fact; no vague praise."
      ),
    }

    return {"research": research, "qualify": qualify, "outreach": outreach}
