/*runmodal.tsx */
"use client";
import { useMemo, useState } from "react";

type InputField = {
  name: string;
  label: string;
  type?: "text" | "email" | "url";
  placeholder?: string;
  required?: boolean;
};

type Workflow = {
  id: string;
  name: string;
  description?: string;
  input_schema?: InputField[];
};



export default function RunModal({
  workflow,
  onStart,
  onClose,
}: {
  workflow: Workflow;
  onStart: (runId: string) => void;
  onClose: () => void;
}) {


  const schema = useMemo<InputField[]>(() => {
    const s = workflow.input_schema ?? [];
    if (s.length > 0) return s;
    // Fallback defaults when schema is missing
    return [
      { name: "company", label: "Company name", type: "text", placeholder: "Acme Corp", required: true },
      { name: "website", label: "Company website", type: "url", placeholder: "https://acme.com", required: false },
      { name: "lead_email", label: "Contact email", type: "email", placeholder: "ceo@acme.com", required: false },
    ];
  }, [workflow]);
  const [values, setValues] = useState<Record<string, string>>(
    Object.fromEntries(schema.map((f) => [f.name, ""]))
  );
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  function setField(name: string, v: string) {
    setValues((prev) => ({ ...prev, [name]: v }));
  }
  const domainWarn =
  (values.website && values.lead_email) &&
  !values.lead_email.toLowerCase().endsWith(new URL(values.website).hostname.replace(/^www\./,""));


  async function start(e: React.FormEvent) {
    e.preventDefault();

      console.log("Form values:", values);
    if (!values.lead_email?.trim()) {
      setErr("Contact email is required");
      return;
    }

    const requiredFields = schema.filter(f => f.required);
    for (const field of requiredFields) {
      const val = values[field.name]?.trim();
      if (!val) {
        setErr(`${field.label} is required`);
        return;
      }

      // Validate company name isn't too vague
      const company = values.company?.trim();
      if (company && company.length < 3) {
        setErr("Company name too short - please enter full company name");
        return;
      }

      // Check for common placeholder values
      const placeholders = ['test', 'example', 'acme', 'company', 'corp', 'inc'];
      if (company && placeholders.includes(company.toLowerCase())) {
        setErr("Please enter a real company name (not a placeholder)");
        return;
      }

      // Warn if company name looks suspicious
      if (company && !/[a-zA-Z]/.test(company)) {
        setErr("Company name should contain letters");
        return;
      }

      
      // Extra validation for email
      if (field.type === "email" && val) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(val)) {
          setErr(`${field.label} must be a valid email`);
          return;
        }
      }
    }  

      setErr(null);
      setBusy(true);
      try {
        const base = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
        const r = await fetch(`${base}/api/workflow-runs`, {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ workflow_id: workflow.id, inputs: values }),
        });
        if (!r.ok) throw new Error(`Run failed (${r.status})`);
        const data: unknown = await r.json();
        const runId = (data as { id?: string }).id;
        if (!runId) throw new Error("No run id returned");
        onStart(runId);
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : String(e);
        setErr(msg);
      } finally {
        setBusy(false);
      }
  }

  const advancedJson = JSON.stringify(values, null, 2);

  return (
    <div className="fixed inset-0 bg-black/30 z-50" onClick={onClose}>
      <div
        className="absolute left-1/2 top-1/2 w-[560px] -translate-x-1/2 -translate-y-1/2 bg-white rounded-2xl border p-4"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="font-semibold">Run “{workflow.name}”</h3>
        {!!workflow.description && (
          <p className="text-sm text-zinc-600 mt-1">{workflow.description}</p>
        )}

    <form onSubmit={start}>
      <div className="mt-3 grid gap-3">
        {schema.map((f) => (
          <label key={f.name} className="block text-sm">
            <span className="text-zinc-700">
              {f.label}{f.required ? " *" : ""}
            </span>
            <input
              type={f.type || "text"}
              required={!!f.required}
              placeholder={f.placeholder}
              value={values[f.name] || ""}
              onChange={(e)=>setField(f.name, e.target.value)}
              className="mt-1 w-full rounded-lg border px-3 py-2"
            />
          </label>
        ))}
      </div>


        <div className="mt-3 text-xs">
          <button
            type="button"
            className="text-zinc-600 underline"
            onClick={() => setShowAdvanced((v) => !v)}
          >
            {showAdvanced ? "Hide Advanced JSON" : "Advanced: Preview JSON"}
          </button>
        </div>
        {showAdvanced && (
          <pre className="mt-2 rounded-lg border bg-zinc-50 p-3 text-xs overflow-auto">
            {advancedJson}
          </pre>
        )}

        {err && <div className="mt-2 text-sm text-rose-600">{err}</div>}
        {domainWarn && (
          <div className="mt-2 text-xs text-amber-700">
            Heads up: the email domain doesn’t match the website. Still continue?
          </div>
        )}
        <div className="mt-3 flex justify-end gap-2">
          <button type="button" onClick={onClose} className="rounded-md border px-3 py-1.5 text-sm">
            Cancel
          </button>
          <button
            type="submit"
            disabled={busy}
            onClick={start}
            className="rounded-md bg-indigo-600 px-3 py-1.5 text-sm text-white hover:bg-indigo-700 disabled:opacity-60"
          >
            {busy ? "Starting..." : "Start run"}
          </button>
        </div>
      </form>
      </div>
    </div>
    
  );
}
