/*stepbuilder.tsx */
"use client";

import type { Step, AgentKind } from "./types";



export default function StepBuilder({ steps, onChange }:{
  steps: Step[]; onChange: (s: Step[]) => void;
}) {
  function addStep() {

    if (steps.length >= 10) {
      alert("Maximum 10 steps allowed");
      return;
    }

    onChange([...steps, { id: crypto.randomUUID(), agent: "research", instructions: "", input_map: {} }]);
  }
  function remove(id: string) {
    onChange(steps.filter(s => s.id !== id));
  }
  function move(id: string, dir: -1|1) {
    const i = steps.findIndex(s => s.id === id);
    if (i < 0) return;
    const j = i + dir;
    if (j < 0 || j >= steps.length) return;
    const copy = steps.slice();
    const [item] = copy.splice(i,1);
    copy.splice(j,0,item);
    onChange(copy);
  }
  function update(id: string, patch: Partial<Step>) {
    onChange(steps.map(s => s.id === id ? { ...s, ...patch } : s));
  }

  const placeholders = {
    research: "Research {{input.company}} and {{input.website}}. Return 3-5 bullets with sources.",
    qualify: "Score fit against ICP. Return JSON: {score:0-100, decision:'yes'|'no'|'maybe', reasons:[...]}",
    outreach: "Write a concise email to {{input.lead_email}} using research. Include one clear CTA."
  };
  

  return (
    <div className="space-y-3">
      {steps.map((s, idx) => (
        <div key={s.id} className="rounded-xl border bg-white p-3 space-y-2">
          <div className="flex items-center justify-between">
            <div className="text-sm text-zinc-500">Step {idx+1}</div>
            <div className="flex gap-2">
              <button type="button" onClick={() => move(s.id,-1)} className="rounded-md border px-2 py-1 text-xs">↑</button>
              <button type="button" onClick={() => move(s.id, 1)} className="rounded-md border px-2 py-1 text-xs">↓</button>
              <button type="button" onClick={() => remove(s.id)} className="rounded-md border px-2 py-1 text-xs text-rose-600 border-rose-200">Delete</button>
            </div>
          </div>
          <label className="block text-sm">
            <span className="text-zinc-700">Agent</span>
            <select value={s.agent} onChange={(e)=>update(s.id,{agent: e.target.value as AgentKind})}
              className="mt-1 w-full rounded-lg border px-3 py-2">
              <option value="research">research</option>
              <option value="qualify">qualify</option>
              <option value="outreach">outreach</option>
            </select>
          </label>
          <label className="block text-sm">
            <span className="text-zinc-700">Instructions (supports {'{{input.company}}'})</span>
            <textarea
             value={s.instructions} 
             onChange={(e)=>update(s.id,{instructions: e.target.value})}
              rows={4} 
              className="mt-1 w-full rounded-lg border px-3 py-2 font-mono text-xs" 
              placeholder={placeholders[s.agent] || "Enter instructions..."} 
              />
          </label>
        </div>
      ))}
      <button type="button" onClick={addStep} className="rounded-lg border px-3 py-1.5 text-sm hover:bg-zinc-50">+ Add step</button>
    </div>
  );
}
