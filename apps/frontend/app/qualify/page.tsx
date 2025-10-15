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

export default function QualifyPage() {
  const [company, setCompany] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [decision, setDecision] = useState<Decision | null>(null);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setDecision(null);
    try {
      const res = await fetch(`${API_BASE}/api/agents/qualify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ company }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(data?.detail || `Request failed with ${res.status}`);
        return;
      }
      setDecision(data?.decision ?? null);
    } catch (err: any) {
      setError(err?.message || 'Network error');
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen p-8 max-w-3xl mx-auto">
      <h1 className="text-3xl font-bold">AgentFlow — Qualify Demo</h1>
      <p className="text-gray-600 mt-2">
        Enter a company. The API will research briefly and return a yes/no fit with reasons.
      </p>

      <form onSubmit={onSubmit} className="mt-6 space-y-4">
        <div>
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
        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={loading}
            className="rounded bg-black text-white px-4 py-2 disabled:opacity-50"
          >
            {loading ? 'Qualifying…' : 'Qualify'}
          </button>
          <span className="text-xs text-gray-500">
            API: {API_BASE}/api/agents/qualify
          </span>
        </div>
      </form>

      {error && (
        <div className="mt-6 rounded border border-red-200 bg-red-50 p-4">
          <div className="font-semibold text-red-700">Error</div>
          <div className="text-red-800 text-sm mt-1">{error}</div>
        </div>
      )}

      {decision && !error && (
        <div className="mt-6 rounded border bg-gray-50 p-4">
          <div className="flex items-center gap-2">
            <div
              className={`h-3 w-3 rounded-full ${
                decision.qualified ? 'bg-green-500' : 'bg-red-500'
              }`}
            />
            <h2 className="text-xl font-semibold">
              {decision.qualified ? 'Qualified' : 'Not Qualified'}
            </h2>
            <span className="ml-2 text-sm text-gray-600">
              Fit score: {decision.fit_score}
            </span>
          </div>

          <div className="mt-3">
            <h3 className="font-medium">Suggested persona</h3>
            <p className="text-gray-700">{decision.suggested_persona || '—'}</p>
          </div>

          <div className="mt-3">
            <h3 className="font-medium">Key hooks</h3>
            <ul className="list-disc ml-6 text-gray-700">
              {decision.key_hooks?.map((k, i) => (
                <li key={i}>{k}</li>
              ))}
            </ul>
          </div>

          <div className="mt-3">
            <h3 className="font-medium">Reasons</h3>
            <ul className="list-disc ml-6 text-gray-700">
              {decision.reasons?.map((r, i) => (
                <li key={i}>{r}</li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </main>
  );
}
