'use client';

import { useState } from 'react';

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';

export default function ResearchPage() {
  const [topic, setTopic] = useState('');
  const [audience, setAudience] = useState('Executive Team');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await fetch(`${API_BASE}/api/agents/research`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic, audience }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        const msg = err?.detail || `Request failed with ${res.status}`;
        setError(msg);
        return;
      }

      const data = await res.json();
      setResult(data?.result ?? '(empty result)');
    } catch (err: any) {
      setError(err?.message || 'Network error');
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen p-8 max-w-3xl mx-auto">
      <h1 className="text-3xl font-bold">AgentFlow — Research Demo</h1>
      <p className="text-gray-600 mt-2">
        Enter a topic and audience. The API will run your agents and return a brief.
      </p>

      <form onSubmit={onSubmit} className="mt-6 space-y-4">
        <div>
          <label className="block text-sm font-medium">Topic</label>
          <input
            className="mt-1 w-full rounded border p-2"
            placeholder="Open-source CRM market 2025"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            required
            minLength={2}
            maxLength={300}
          />
        </div>
        <div>
          <label className="block text-sm font-medium">Audience</label>
          <input
            className="mt-1 w-full rounded border p-2"
            placeholder="Executive Team"
            value={audience}
            onChange={(e) => setAudience(e.target.value)}
            minLength={2}
            maxLength={120}
          />
        </div>

        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={loading}
            className="rounded bg-black text-white px-4 py-2 disabled:opacity-50"
          >
            {loading ? 'Running…' : 'Run Research'}
          </button>
          <span className="text-xs text-gray-500">
            API: {API_BASE}/api/agents/research
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

      {/* Result */}
      {result && !error && (
        <div className="mt-6">
          <h2 className="text-xl font-semibold">Result</h2>
          <pre className="mt-2 whitespace-pre-wrap rounded border bg-gray-50 p-4 text-sm">
            {result}
          </pre>
        </div>
      )}
    </main>
  );
}
