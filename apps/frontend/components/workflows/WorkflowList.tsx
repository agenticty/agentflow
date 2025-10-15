/*Workflowlist.tsx*/
"use client";

import { useEffect, useState } from "react";
import Alert from "@/components/ui/Alert";
import { Skeleton } from "@/components/ui/Skeleton";
import { Badge } from "@/components/ui/Badge";
import LogDrawer from "@/components/workflows/LogDrawer";
import RunModal from "@/components/workflows/RunModal";
import { apiDeleteWorkflow } from "@/lib/api";
import EmptyStateTemplate from "./EmptyStateTemplate";

async function createInboundTemplate() {
  const base = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
  const payload = {
    name: "Research-Qualify-Outreach Workflow",
    description:
      "Give us a company and contact — we’ll research them, check fit, and draft a personalized email.",
    trigger: { type: "webhook", path: "/lead" },
    input_schema: [
      { name: "company", label: "Company name", type: "text", placeholder: "Acme Corp", required: true },
      { name: "website", label: "Company website", type: "url", placeholder: "https://acme.com", required: false },
      { name: "lead_email", label: "Contact email", type: "email", placeholder: "ceo@acme.com", required: true },
      { name: "contact_name", label: "Contact name (optional)", 
        type: "text", placeholder: "Sam Altman", required: false }
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
  if (!r.ok) throw new Error(`Failed to create template (${r.status})`);
}




type Trigger = { type: string; path?: string };
type InputField = {
  name: string;
  label: string;
  type?: "text" | "email" | "url";
  placeholder?: string;
  required?: boolean;
};
type StepLite = {
  id: string;
  agent: string;
  instructions?: string;
  input_map?: Record<string, unknown>;
};
type Workflow = {
  id: string;
  name: string;
  description?: string;
  trigger: Trigger;
  steps: StepLite[];
  input_schema?: InputField[];
};

function getErrorMessage(e: unknown): string {
  return e instanceof Error ? e.message : "Unexpected error";
}

export default function WorkflowList({ configured }:{ configured: boolean }) {
  const [data, setData] = useState<Workflow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [logRunId, setLogRunId] = useState<string | null>(null);
  const [runFor, setRunFor] = useState<string | null>(null);

  // Create the template when the URL has ?template=automate-inbound
useEffect(() => {
  const url = new URL(window.location.href);
  if (url.searchParams.get("template") === "automate-inbound") {
    (async () => {
      try {
        await createInboundTemplate();
      } catch (e) {
        console.error(e);
        alert("Failed to create template. Check API.");
      } finally {
        // clean the query and refresh list
        url.searchParams.delete("template");
        window.history.replaceState({}, "", url.toString());
        location.reload();
      }
    })();
  }
}, []);


  useEffect(() => {
    (async () => {
    
      try {
        const base = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";
        const list = await fetch(`${base}/api/workflows`, { cache: "no-store" });
        if (!list.ok) throw new Error(`Could not fetch workflows (${list.status})`);
        const json = (await list.json()) as Workflow[];
        setData(json);
      } catch (e: unknown) {
        setError(getErrorMessage(e));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  async function handleDelete(id: string) {
    if (!confirm("Delete this workflow?")) return;
    try {
      await apiDeleteWorkflow(id);
      setData((prev) => (prev ? prev.filter((w) => w.id !== id) : prev));
    } catch (e: unknown) {
      setError(getErrorMessage(e));
    }
  }

  if (loading)
    return (
      <div className="space-y-3">
        <Skeleton className="h-24" />
        <Skeleton className="h-24" />
        <Skeleton className="h-24" />
      </div>
    );

  if (error) return <Alert kind="error" title="Couldn’t load workflows" body={error} />;

  if (!data || data.length === 0) {
    return <EmptyStateTemplate />;
  }

  return (
    <>
      <ul className="grid gap-4">
        {data.map((wf) => (
          <li key={wf.id} className="rounded-xl border bg-white p-5 hover:shadow-sm transition">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h3 className="font-semibold">{wf.name}</h3>
                <p className="text-sm text-zinc-600 mt-1">
                  {wf.description || "Give a company & contact. We research, check fit, and draft an email. We stop if evidence is weak."}
                </p>
              </div>
              <Badge>{wf.steps?.length ?? 0} steps</Badge>
            </div>

            <div className="mt-3 text-sm text-zinc-700">Your AI employees on the job:</div>
            <div className="mt-2 flex flex-wrap gap-2">
              {wf.steps?.map((s) => (
                <span key={s.id} className="text-xs rounded-md bg-zinc-100 px-2 py-1">
                  {s.agent}
                </span>
              ))}
            </div>

            <div className="mt-4 flex flex-wrap gap-3">
              <button
                onClick={() => configured ? setRunFor(wf.id) : (location.href = "/settings")}
                className={`rounded-lg border px-3 py-1.5 text-sm hover:bg-zinc-50 ${!configured ? "opacity-60" : ""}`}
                title={configured ? "Run Autopilot" : "Finish setup first"}
              >
                {configured ? "Run" : "Finish setup"}
              </button>
              <button onClick={() => setLogRunId(prompt("Enter Run ID to view logs:") || "")} className="rounded-lg border px-3 py-1.5 text-sm hover:bg-zinc-50">
                Logs
              </button>
              <button onClick={() => handleDelete(wf.id)} className="rounded-lg border px-3 py-1.5 text-sm text-rose-600 border-rose-200 hover:bg-rose-50">
                Delete
              </button>
            </div>
          </li>
        ))}
      </ul>

      {runFor && (
        <RunModal
          workflow={data.find(w => w.id === runFor)!}
          onStart={(rid) => { setRunFor(null); setLogRunId(rid); }}
          onClose={() => setRunFor(null)}
        />
      )}

      {logRunId && logRunId !== "" && (
        <LogDrawer runId={logRunId} onClose={() => setLogRunId(null)} />
      )}


    </>
  );
}
