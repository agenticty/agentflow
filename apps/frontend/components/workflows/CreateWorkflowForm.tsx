/*createworkflowform.tsx*/ 
"use client";

import { useState } from "react";
import Spinner from "@/components/ui/Spinner";
import Alert from "@/components/ui/Alert";
import StepBuilder from "./StepBuilder";
import type { Step } from "./types";

export default function CreateWorkflowForm() {
  const [name, setName] = useState("");
  const [steps, setSteps] = useState<Step[]>([
    { id: crypto.randomUUID(), agent: "research", instructions: "Research {{input.company}} with citations.", input_map: {} },
    { id: crypto.randomUUID(), agent: "qualify",  instructions: "Score fit from the research; return JSON {score,reasons,decision}.", input_map: {} },
    { id: crypto.randomUUID(), agent: "outreach", instructions: "Write a concise personalized email using the research.", input_map: {} },
  ]);
  const [busy, setBusy] = useState(false);
  const [ok, setOk] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setErr(null); setOk(null);

    try {

      if (steps.length === 0) {
        throw new Error("Add at least one step");
      }
      
      for (const step of steps) {
        if (!step.instructions?.trim()) {
          throw new Error(`Step ${steps.indexOf(step) + 1} needs instructions`);
        }
      }

      const defaultSchema = [
        { name: "company", label: "Company name", type: "text", placeholder: "Acme Corp", required: true },
        { name: "website", label: "Company website", type: "url", placeholder: "https://acme.com", required: false },
        { name: "lead_email", label: "Contact email", type: "email", placeholder: "ceo@acme.com", required: true },
      ];
      const payload = {
        name,
        description: "Give us a company and contact — we’ll research them, check fit, and draft a personalized email.",
        trigger: { type: "webhook", path: "/lead" },
        steps,
        input_schema: defaultSchema, // <-- add this
      };
      const api = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";
      const r = await fetch(`${api}/api/workflows`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!r.ok) throw new Error(`API responded ${r.status}`);
      setOk("Workflow created successfully.");
      setName("");
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } catch (e:any) {
      setErr(e.message || "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }


  return (
    <form onSubmit={submit} className="rounded-xl border bg-white p-5 space-y-4">
      <h3 className="font-semibold">Create Workflow</h3>

      {ok && <Alert kind="success" title="Success" body={ok} />}
      {err && <Alert kind="error" title="Error" body={err} />}

      <label className="block text-sm">
        <span className="text-zinc-700">Name</span>
        <input
          value={name}
          onChange={(ev) => setName(ev.target.value)}
          placeholder="Inbound Lead → Research → Outreach"
          className="mt-1 w-full rounded-lg border px-3 py-2"
          required
        />
      </label>

      <StepBuilder steps={steps} onChange={setSteps} />

      <button
        disabled={busy}
        className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-3.5 py-2 text-white hover:bg-indigo-700 disabled:opacity-60"
      >
        {busy ? <Spinner /> : null}
        {busy ? "Creating..." : "Create"}
      </button>
    </form>
  );
}
