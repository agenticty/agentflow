'use client';

import { useState } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';

type Decision = {
  qualified: boolean;
  fit_score: number;
  reasons: string[];
  suggested_persona: string;
  key_hooks: string[];
};

type WorkflowResponse = {
  status: 'success' | 'error';
  research?: string | null;
  decision?: Decision | null;
  outreach?: { subject: string; body: string } | null;
};

export default function FullWorkflowPage() {
  const [company, setCompany] = useState('');
  const [persona, setPersona] = useState('RevOps Lead');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<WorkflowResponse | null>(null);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setData(null);

    try {
      const res = await fetch(`${API_BASE}/api/agents/full-workflow`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ company, persona }),
      });

      const json = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(json?.detail || `Request failed with ${res.status}`);
        return;
      }
      setData(json);
    } catch (err: any) {
      setError(err?.message || 'Network error');
    } finally {
      setLoading(false);
    }
  }

  const decision = data?.decision as Decision | undefined;

  return (
    <main className="min-h-screen p-8 max-w-4xl mx-auto">
      <h1 className="text-3xl font-bold">AgentFlow — Full Workflow Demo</h1>
      <p className="text-gray-600 mt-2">
        Runs research → qualify → (if qualified) outreach, then shows all outputs.
      </p>

      <form onSubmit={onSubmit} className="mt-6 grid gap-4 sm:grid-cols-2">
        <div className="sm:col-span-1">
          <label className="block text-sm font-medium">Company</label>
          <input
            className="mt-1 w-full rounded border p-2"
            placeholder="Salesforce"
            value={company}
            onChange={(e) => setCompany(e.target.value)}
            required
            minLength={2}
            maxLength={200}
          />
        </div>
        <div className="sm:col-span-1">
          <label className="block text-sm font-medium">Persona</label>
          <input
            className="mt-1 w-full rounded border p-2"
            placeholder="RevOps Lead"
            value={persona}
            onChange={(e) => setPersona(e.target.value)}
            minLength={2}
            maxLength={120}
          />
        </div>
        <div className="sm:col-span-2 flex items-center gap-3">
          <button
            type="submit"
            disabled={loading}
            className="rounded bg-black text-white px-4 py-2 disabled:opacity-50"
          >
            {loading ? 'Running…' : 'Run Full Workflow'}
          </button>
          <span className="text-xs text-gray-500">
            API: {API_BASE}/api/agents/full-workflow
          </span>
        </div>
      </form>

      {/* Error */}
      {error && (
        <div className="mt-6 rounded border border-red-200 bg-red-50 p-4">
          <div className="font-semibold text-red-700">Error</div>
          <div className="text-red-800 text-sm mt-1">{error}</div>
        </div>
      )}

      {/* Results */}
      {data && !error && (
        <section className="mt-8 space-y-6">
          {/* Research */}
          <div className="rounded border bg-gray-50 p-4">
            <h2 className="text-xl font-semibold">Research</h2>
            <pre className="mt-2 whitespace-pre-wrap text-sm">
              {data.research || '—'}
            </pre>
          </div>

          {/* Decision */}
          <div className="rounded border bg-gray-50 p-4">
            <h2 className="text-xl font-semibold">Decision</h2>
            {decision ? (
              <div className="mt-2 space-y-2 text-sm">
                <div className="flex items-center gap-2">
                  <div
                    className={`h-3 w-3 rounded-full ${
                      decision.qualified ? 'bg-green-500' : 'bg-red-500'
                    }`}
                  />
                  <span className="font-medium">
                    {decision.qualified ? 'Qualified' : 'Not Qualified'}
                  </span>
                  <span className="text-gray-600">Score: {decision.fit_score}</span>
                </div>
                <div>
                  <div className="font-medium">Suggested persona</div>
                  <div className="text-gray-700">{decision.suggested_persona || '—'}</div>
                </div>
                <div>
                  <div className="font-medium">Key hooks</div>
                  <ul className="list-disc ml-6 text-gray-700">
                    {decision.key_hooks?.map((k, i) => <li key={i}>{k}</li>)}
                  </ul>
                </div>
                <div>
                  <div className="font-medium">Reasons</div>
                  <ul className="list-disc ml-6 text-gray-700">
                    {decision.reasons?.map((r, i) => <li key={i}>{r}</li>)}
                  </ul>
                </div>
              </div>
            ) : (
              <div className="text-sm text-gray-600">—</div>
            )}
          </div>

          {/* Outreach */}
          <div className="rounded border bg-gray-50 p-4">
            <h2 className="text-xl font-semibold">Outreach</h2>
            {data.outreach ? (
              <>
                <div className="mt-2">
                  <div className="font-medium">Subject</div>
                  <div className="text-gray-800">{data.outreach.subject}</div>
                </div>
                <div className="mt-3">
                  <div className="font-medium">Body</div>
                  <pre className="whitespace-pre-wrap text-sm mt-1">
                    {data.outreach.body}
                  </pre>
                </div>
              </>
            ) : (
              <div className="text-sm text-gray-600">No outreach generated.</div>
            )}
          </div>
        </section>
      )}
    </main>
  );
}
