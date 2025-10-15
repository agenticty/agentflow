const BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export async function apiDeleteWorkflow(id: string) {
  const r = await fetch(`${BASE}/api/workflows/${id}`, { method: "DELETE" });
  if (!r.ok) throw new Error(`Delete failed (${r.status})`);
}

export async function apiRunWorkflow(id: string) {
  const r = await fetch(`${BASE}/api/workflow-runs`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ workflow_id: id, inputs: {} })
  });
  if (!r.ok) throw new Error(`Run failed (${r.status})`);
  return r.json() as Promise<{ id: string; workflow_id: string; status: string }>;
}
