"use client";

export default function UseInboundTemplateButton() {
  async function onClick() {
    const base = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
    const payload = {
      name: "Research-Qualify-Outreach Workflow",
      description:
        "Give us a company and contact — we’ll research them, check fit, and draft a personalized email.",
      trigger: { type: "webhook", path: "/lead" },
      input_schema: [
        { name: "company", label: "Company name", type: "text", placeholder: "Acme Corp", required: true },
        { name: "website", label: "Company website", type: "url", placeholder: "https://acme.com", required: false },
        { name: "lead_email", label: "Contact email", type: "email", placeholder: "ceo@acme.com", required: true }
      ],
      steps: [
        {
          id: crypto.randomUUID(),
          agent: "research",
          instructions:
            "Research {{input.company}} (and {{input.website}} if given). Return 3–5 bullets with recent sources.",
          input_map: {}
        },
        {
          id: crypto.randomUUID(),
          agent: "qualify",
          instructions:
            "Score fit based on the research. Return JSON {score:0-100, reasons:[...], decision:'yes'|'no'|'maybe'}.",
          input_map: {}
        },
        {
          id: crypto.randomUUID(),
          agent: "outreach",
          instructions:
            "Write a concise, friendly email to {{input.lead_email}} using the research. One clear CTA.",
          input_map: {}
        }
      ]
    };
    const r = await fetch(`${base}/api/workflows`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!r.ok) return alert(`Failed to create template (${r.status})`);
    location.reload();
  }

  return (
    <button onClick={onClick} className="rounded-lg border px-3 py-1.5 text-sm hover:bg-zinc-50">
      Use “Research-Qualify-Outreach Workflow”
    </button>
  );
}
