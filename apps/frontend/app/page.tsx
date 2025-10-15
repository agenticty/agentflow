/* eslint-disable @typescript-eslint/no-explicit-any */
"use client";


import { useEffect, useState } from "react";
import StatusPill from "@/components/ui/StatusPill";


export default function Landing() {
  const [org, setOrg] = useState<any>(null);
  const ok = !!org?.ready;

  useEffect(() => {
    (async () => {
      const base = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
      const r = await fetch(`${base}/api/org/profile?t=${Date.now()}`, { cache: "no-store" });
      if (r.ok) setOrg(await r.json());
    })();
  }, []);

  return (
    <div className="grid gap-10 lg:grid-cols-2 items-center">
      <section className="space-y-5">
        <div className="flex items-center gap-3">
          <h1 className="text-4xl font-semibold tracking-tight">We check every prospect against your ICP before you reach out.</h1>
        </div>

        <p className="text-zinc-700">
          Give us a company and a contact. We’ll <b>research</b> them, <b>check fit</b> against your ICP,
          and <b>draft a tailored email</b>. If there isn’t enough evidence or they’re not a fit,
          we stop and tell you why.
        </p>
        <StatusPill ok={ok} />

        <div className="flex gap-3">
          <a
            href="/settings"
            className="inline-flex items-center rounded-lg bg-indigo-600 px-4 py-2.5 text-white hover:bg-indigo-700"
          >
            Add Your Company Details (setup) 
          </a>
          <a
            href="/app"
            className="inline-flex items-center rounded-lg border px-4 py-2.5 hover:bg-zinc-50"
          >
            Open App
          </a>
        </div>

        <ul className="mt-2 grid gap-2 text-sm text-zinc-700">
          <li className="flex items-center gap-2">
            <span className="size-1.5 rounded-full bg-emerald-500" />
            Cites recent sources (no guesses)
          </li>
          <li className="flex items-center gap-2">
            <span className="size-1.5 rounded-full bg-emerald-500" />
            Scores fit against your ICP
          </li>
          <li className="flex items-center gap-2">
            <span className="size-1.5 rounded-full bg-emerald-500" />
            Writes in your voice (one-liner + value props)
          </li>
        </ul>
      </section>

      <section className="rounded-2xl border bg-white p-6 shadow-sm">
        <div className="text-sm text-zinc-500">Workflow Preview</div>
        <div className="mt-3 rounded-xl border bg-zinc-50 p-4">
          <div className="flex items-center justify-between">
            <div className="font-medium">Research-Qualify-Outreach Workflow</div>
            {/*<span className={`text-xs rounded-full px-2 py-0.5 ${ok ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}>
              {ok ? "Configured" : "Setup needed"}
            </span>*/}
          </div>
          <ol className="mt-3 space-y-2 text-sm">
            <li>1. Research company — <span className="text-emerald-600">done</span></li>
            <li>2. Check fit (ICP) — <span className="text-emerald-600">done</span></li>
            <li>3. Draft outreach email — <span className="text-emerald-600">done</span></li>
          </ol>
        </div>
      </section>

      {/* Below the fold */}
      <section className="lg:col-span-2 rounded-2xl border bg-white p-6">
        <h2 className="text-xl font-semibold">How it works</h2>
        <div className="mt-4 grid gap-4 sm:grid-cols-3">
          <div className="rounded-xl border p-4">
            <div className="text-sm text-zinc-500">Step 1</div>
            <div className="font-medium">Set up your company details</div>
            <p className="text-sm text-zinc-600 mt-1">Tell us about your business (2 minutes) or auto-fill from your website.</p>
          </div>
          <div className="rounded-xl border p-4">
            <div className="text-sm text-zinc-500">Step 2</div>
            <div className="font-medium">Open the app</div>
            <p className="text-sm text-zinc-600 mt-1">Enter a company + email and click “Run Autopilot”.</p>
          </div>
          <div className="rounded-xl border p-4">
            <div className="text-sm text-zinc-500">Step 3</div>
            <div className="font-medium">We do the work</div>
            <p className="text-sm text-zinc-600 mt-1">Research → qualify → draft. We stop if evidence is weak.</p>
          </div>
        </div>
      </section>
    </div>
  );
}
  