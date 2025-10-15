'use client';

import { useState } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';

export default function OutreachPage() {
  const [company, setCompany] = useState('');
  const [persona, setPersona] = useState('RevOps Lead');
  const [hooks, setHooks] = useState('faster lead handling, reduced manual ops, scalable outreach');
  const [context, setContext] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [subject, setSubject] = useState<string | null>(null);
  const [body, setBody] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setSubject(null);
    setBody(null);

    const hooksArray = hooks
      .split(',')
      .map((h) => h.trim())
      .filter(Boolean);

    try {
      const res = await fetch(`${API_BASE}/api/agents/outreach`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          company,
          persona,
          hooks: hooksArray.length ? hooksArray : undefined,
          context: context.trim() || undefined,
        }),
      });

      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(data?.detail || `Request failed with ${res.status}`);
        return;
      }
      setSubject(data?.subject ?? null);
      setBody(data?.body ?? null);
    } catch (err: any) {
      setError(err?.message || 'Network error');
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen p-8 max-w-3xl mx-auto">
      <h1 className="text-3xl font-bold">AgentFlow — Outreach Demo</h1>
      <p className="text-gray-600 mt-2">
        Provide a company and optional context. If context is provided, the writer won’t research.
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

        <div>
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

        <div>
          <label className="block text-sm font-medium">Value props (comma-separated)</label>
          <input
            className="mt-1 w-full rounded border p-2"
            value={hooks}
            onChange={(e) => setHooks(e.target.value)}
          />
        </div>

        <div>
          <label className="block text-sm font-medium">Optional context (no research if provided)</label>
          <textarea
            className="mt-1 w-full rounded border p-2 h-28"
            placeholder="Paste bullets or notes here..."
            value={context}
            onChange={(e) => setContext(e.target.value)}
          />
        </div>

        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={loading}
            className="rounded bg-black text-white px-4 py-2 disabled:opacity-50"
          >
            {loading ? 'Drafting…' : 'Draft Email'}
          </button>
          <span className="text-xs text-gray-500">
            API: {API_BASE}/api/agents/outreach
          </span>
        </div>
      </form>

      {error && (
        <div className="mt-6 rounded border border-red-200 bg-red-50 p-4">
          <div className="font-semibold text-red-700">Error</div>
          <div className="text-red-800 text-sm mt-1">{error}</div>
        </div>
      )}

      {(subject || body) && !error && (
        <div className="mt-6 rounded border bg-gray-50 p-4">
          <h2 className="text-xl font-semibold">Email Draft</h2>
          <div className="mt-3">
            <div className="font-medium text-gray-800">Subject</div>
            <div className="text-gray-700">{subject}</div>
          </div>
          <div className="mt-3">
            <div className="font-medium text-gray-800">Body</div>
            <pre className="whitespace-pre-wrap text-sm mt-1">{body}</pre>
          </div>
        </div>
      )}
    </main>
  );
}
