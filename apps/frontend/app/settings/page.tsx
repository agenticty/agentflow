/* eslint-disable @typescript-eslint/no-explicit-any */
"use client";

import { useEffect, useState } from "react";

type Org = {
  name?: string;
  product_one_liner?: string;
  value_props?: string[];
  icp?: {
    industries?: string[];
    employee_range?: { min?: number; max?: number };
    regions?: string[];
    roles?: string[];
    tech_signals?: string[];
  };
  disqualifiers?: string[];
  outreach_footer?: string;
  tone?: { style?: string; length?: string };
  ready?: boolean;
};

export default function SettingsPage() {
  // Server state
  const [initial, setInitial] = useState<Org | null>(null);
  const [ready, setReady] = useState<boolean>(false);

  const [industriesText, setIndustriesText] = useState("");
  const [techText, setTechText] = useState("");
  const [regionsText, setRegionsText] = useState("");
  const [rolesText, setRolesText] = useState("");
  const [disqText, setDisqText] = useState("");
  const [minEmpText, setMinEmpText] = useState("");
  const [maxEmpText, setMaxEmpText] = useState("");

  // Editable form (start empty so nothing looks "mysteriously filled")
  const [form, setForm] = useState<Org>({
    name: "",
    product_one_liner: "",
    value_props: [],
    icp: {
      industries: [],
      employee_range: { min: 0, max: 1000000 },
      regions: [],
      roles: [],
      tech_signals: [],
    },
    disqualifiers: [],
    outreach_footer: "",
    tone: { style: "friendly", length: "short" },
  });

  // Autofill (draft) state
  const [siteUrl, setSiteUrl] = useState("");
  const [draft, setDraft] = useState<any | null>(null);
  const [draftWarn, setDraftWarn] = useState<string | null>(null);

  // UI state
  const [busy, setBusy] = useState(false);
  const [okMsg, setOkMsg] = useState<string | null>(null);
  const [errMsg, setErrMsg] = useState<string | null>(null);

  // Helpers
  const base = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
  const changed = JSON.stringify(form) !== JSON.stringify(initial || {});

  function set(path: string, value: any) {
    const segs = path.split(".");
    setForm((prev: any) => {
      const copy: any = structuredClone(prev || {});
      // eslint-disable-next-line prefer-const
      let cur = copy;
      for (let i = 0; i < segs.length - 1; i++) cur[segs[i]] ||= {};
      cur[segs.at(-1)!] = value;
      return copy;
    });
  }
  
  const arrToCsv = (a?: string[]) => (a || []).join(", ");

  // Load current profile
  useEffect(() => {
    setIndustriesText((form.icp?.industries || []).join(", "));
    setTechText((form.icp?.tech_signals || []).join(", "));
    setRegionsText((form.icp?.regions || []).join(", "));
    setRolesText((form.icp?.roles || []).join(", "));
    setDisqText((form.disqualifiers || []).join(", "));
    setMinEmpText(
      form.icp?.employee_range?.min !== undefined ? String(form.icp.employee_range.min) : ""
    );
    setMaxEmpText(
      form.icp?.employee_range?.max !== undefined ? String(form.icp.employee_range.max) : ""
    );
    (async () => {
      const base = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
    const r = await fetch(`${base}/api/org/profile?t=${Date.now()}`, { cache: "no-store" });
    if (!r.ok) return;
    const data = await r.json();

    // persist full object
    setInitial(data);
    setForm((prev:any) => ({ ...(prev||{}), ...(data||{}) }));

    // hydrate the text inputs (so the fields show what’s saved)
    setIndustriesText((data.icp?.industries || []).join(", "));
    setTechText((data.icp?.tech_signals || []).join(", "));
    setRegionsText((data.icp?.regions || []).join(", "));
    setRolesText((data.icp?.roles || []).join(", "));
    setDisqText((data.disqualifiers || []).join(", "));
    setMinEmpText(
      data.icp?.employee_range?.min !== undefined ? String(data.icp.employee_range.min) : ""
    );
    setMaxEmpText(
      data.icp?.employee_range?.max !== undefined ? String(data.icp.employee_range.max) : ""
    );
      try {
        const r = await fetch(`${base}/api/org/profile?t=${Date.now()}`, { cache: "no-store" });
        if (!r.ok) return;
        const data: Org = await r.json();
        setInitial(data);
        setReady(!!data?.ready);
        // Prefill form with saved profile (if any) so users can edit what THEY saved
        if (data && Object.keys(data).length) {
          // ensure arrays/objects exist
          setForm({
            name: data.name || "",
            product_one_liner: data.product_one_liner || "",
            value_props: data.value_props || [],
            icp: {
              industries: data.icp?.industries || [],
              employee_range: {
                min: data.icp?.employee_range?.min ?? 0,
                max: data.icp?.employee_range?.max ?? 1000000,
              },
              regions: data.icp?.regions || [],
              roles: data.icp?.roles || [],
              tech_signals: data.icp?.tech_signals || [],
            },
            disqualifiers: data.disqualifiers || [],
            outreach_footer: data.outreach_footer || "",
            tone: {
              style: data.tone?.style || "friendly",
              length: data.tone?.length || "short",
            },
          });
        }
      } catch {
        // ignore
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const csvToArr = (s: string) => s.split(",").map(t => t.trim()).filter(Boolean);

    // helpers to commit on blur (or on Save if you prefer)
  const commitIndustries = () => set("icp.industries", csvToArr(industriesText));
  const commitTech = () => set("icp.tech_signals", csvToArr(techText));
  const commitRegions = () => set("icp.regions", csvToArr(regionsText));
  const commitRoles = () => set("icp.roles", csvToArr(rolesText));
  const commitDisq = () => set("disqualifiers", csvToArr(disqText));
  const commitMin = () => set("icp.employee_range.min", minEmpText ? parseInt(minEmpText,10) : undefined);
  const commitMax = () => set("icp.employee_range.max", maxEmpText ? parseInt(maxEmpText,10) : undefined);

  // Autofill from website (fast, with client timeout)
  async function fillFromWebsite() {
    setOkMsg(null); setErrMsg(null); setDraft(null); setDraftWarn(null);
    if (!siteUrl) { setErrMsg("Please enter a website URL first."); return; }
    setBusy(true);
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 15000); // 15s cap
    try {
      const r = await fetch(`${base}/api/org/from-url`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ url: siteUrl }),
        signal: ctrl.signal,
      });
      const data = await r.json();
      setDraft(data?.draft || null);
      setDraftWarn(data?.warning || null);
      if (data?.draft) setOkMsg("Draft ready. Review below and click 'Apply draft'.");
      else if (data?.warning) setErrMsg(data.warning);
      else setErrMsg("No draft produced. Try another page URL or fill manually.");
    } catch {
      setErrMsg("Timed out or failed to fetch website. Try again or fill manually.");
    } finally {
      clearTimeout(timer);
      setBusy(false);
    }
  }

  function applyDraft() {
    if (!draft) return;
    setForm((prev: any) => ({
      ...(prev || {}),
      name: draft.name || prev?.name || "",
      product_one_liner: draft.product_one_liner || prev?.product_one_liner || "",
      value_props: Array.isArray(draft.value_props) && draft.value_props.length ? draft.value_props : (prev?.value_props || []),
      icp: {
        ...(prev?.icp || {}),
        ...(draft.icp || {}),
        employee_range: {
          min: draft.icp?.employee_range?.min ?? prev?.icp?.employee_range?.min ?? 0,
          max: draft.icp?.employee_range?.max ?? prev?.icp?.employee_range?.max ?? 1000000,
        },
      },
    }));
    setDraft(null);
    setDraftWarn(null);
    setOkMsg("Draft applied. Review the fields and click Save.");
  }



  async function save() {
    setOkMsg(null); setErrMsg(null); setBusy(true);
  
    // 1) Build ICP from current text boxes (no need to blur first)
    const csv = (s: string) => s.split(",").map(t=>t.trim()).filter(Boolean);
    const nextForm = {
      ...form,
      icp: {
        ...(form.icp || {}),
        industries: csv(industriesText),
        tech_signals: csv(techText),
        regions: csv(regionsText),
        roles: csv(rolesText),
        employee_range: {
          min: minEmpText ? parseInt(minEmpText, 10) : undefined,
          max: maxEmpText ? parseInt(maxEmpText, 10) : undefined,
        },
      },
      disqualifiers: csv(disqText),
    };
  
    try {
      const base = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
      const r = await fetch(`${base}/api/org/profile`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(nextForm),
      });
      if (!r.ok) throw new Error("Save failed.");
  
      // 2) Update local state from what we just saved
      setForm(nextForm);
      setInitial(nextForm);
      setOkMsg("Saved. You’re ready to run!");
    } catch (e:any) {
      setErrMsg(e.message || "Error saving.");
    } finally {
      setBusy(false);
    }
  }
  

  return (
    <div className="max-w-3xl space-y-5">
      {/* Status banner (server truth) */}
      <div
        className={`rounded-xl border px-4 py-3 ${
          ready
            ? "bg-emerald-50 border-emerald-200 text-emerald-800"
            : "bg-amber-50 border-amber-200 text-amber-800"
        }`}
      >
        {ready
          ? "You're all set! You can run the workflow now."
          : "Setup needed. Fill this in once (about 2 minutes)."}
      </div>

      <h1 className="text-2xl font-semibold">Organization Settings</h1>

      {/* Autofill control */}
      <div className="rounded-xl border p-4 bg-white">
        <label className="block text-sm">
          <span className="text-zinc-700">Company website (auto-fill your profile)</span>
          <div className="mt-1 flex gap-2">
            <input
              value={siteUrl}
              onChange={(e) => setSiteUrl(e.target.value)}
              placeholder="https://yourcompany.com"
              className="flex-1 rounded-lg border px-3 py-2"
              inputMode="url"
            />
            <button
              type="button"
              onClick={fillFromWebsite}
              className="rounded-lg border px-3 py-2 hover:bg-zinc-50 disabled:opacity-60"
              disabled={busy || !siteUrl}
            >
              {busy ? "Filling…" : "Fill from website"}
            </button>
          </div>
          <p className="text-xs text-zinc-500 mt-1">
            We’ll draft your one-liner, ICP, and value props. Review the draft before applying.
          </p>
        </label>

        {(draft || draftWarn) && (
          <div className="mt-3 rounded-xl border p-3">
            <div className="flex items-start justify-between">
              <div className="font-medium">Draft from website</div>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => { setDraft(null); setDraftWarn(null); }}
                  className="rounded-md border px-3 py-1.5 text-sm"
                >
                  Discard
                </button>
                <button
                  type="button"
                  onClick={applyDraft}
                  disabled={!draft}
                  className="rounded-md bg-indigo-600 px-3 py-1.5 text-sm text-white disabled:opacity-60"
                >
                  Apply draft
                </button>
              </div>
            </div>
            {draftWarn && <div className="text-xs text-amber-700 mt-1">{draftWarn}</div>}
            {draft && (
              <pre className="mt-2 rounded-lg border bg-zinc-50 p-3 text-xs overflow-auto">
                {JSON.stringify(draft, null, 2)}
              </pre>
            )}
          </div>
        )}
      </div>

      {/* Core facts */}
      <div className="rounded-xl border p-4 bg-white space-y-3">
        <label className="block text-sm">
          <span className="text-zinc-700">Company name *</span>
          <input
            value={form.name || ""}
            onChange={(e) => set("name", e.target.value)}
            className="mt-1 w-full rounded-lg border px-3 py-2"
          />
        </label>

        <label className="block text-sm">
          <span className="text-zinc-700">Product one-liner *</span>
          <input
            value={form.product_one_liner || ""}
            onChange={(e) => set("product_one_liner", e.target.value)}
            className="mt-1 w-full rounded-lg border px-3 py-2"
          />
          <p className="text-xs text-zinc-500 mt-1">
            E.g., “We automate inbound lead research and personalized outreach for B2B teams.”
          </p>
        </label>

        <label className="block text-sm">
          <span className="text-zinc-700">Value props (comma-separated) *</span>
          <input
            value={arrToCsv(form.value_props)}
            onChange={(e) => set("value_props", csvToArr(e.target.value))}
            className="mt-1 w-full rounded-lg border px-3 py-2"
          />
        </label>
      </div>

      {/* ICP & rules */}
      {/* --- Replace your ICP UI block with this --- */}
      <div className="rounded-xl border p-4 bg-white space-y-3">
        <h2 className="font-medium">Ideal Customer Profile</h2>
        <div className="grid sm:grid-cols-2 gap-3">
          <label className="block text-sm">
            <span className="text-zinc-700">Industries (comma-separated)</span>
            <input
              value={industriesText}
              onChange={(e)=>setIndustriesText(e.target.value)}
              onBlur={commitIndustries}
              className="mt-1 w-full rounded-lg border px-3 py-2"
            />
          </label>
          <label className="block text-sm">
            <span className="text-zinc-700">Tech signals (comma-separated)</span>
            <input
              value={techText}
              onChange={(e)=>setTechText(e.target.value)}
              onBlur={commitTech}
              className="mt-1 w-full rounded-lg border px-3 py-2"
            />
          </label>
          <label className="block text-sm">
            <span className="text-zinc-700">Min employees</span>
            <input
              type="text" /* use text to allow partial edits */
              inputMode="numeric"
              value={minEmpText}
              onChange={(e)=>setMinEmpText(e.target.value)}
              onBlur={commitMin}
              className="mt-1 w-full rounded-lg border px-3 py-2"
              placeholder="e.g. 20"
            />
          </label>
          <label className="block text-sm">
            <span className="text-zinc-700">Max employees</span>
            <input
              type="text"
              inputMode="numeric"
              value={maxEmpText}
              onChange={(e)=>setMaxEmpText(e.target.value)}
              onBlur={commitMax}
              className="mt-1 w-full rounded-lg border px-3 py-2"
              placeholder="e.g. 1000"
            />
          </label>
          <label className="block text-sm">
            <span className="text-zinc-700">Regions (comma-separated)</span>
            <input
              value={regionsText}
              onChange={(e)=>setRegionsText(e.target.value)}
              onBlur={commitRegions}
              className="mt-1 w-full rounded-lg border px-3 py-2"
            />
          </label>
          <label className="block text-sm">
            <span className="text-zinc-700">Roles (comma-separated)</span>
            <input
              value={rolesText}
              onChange={(e)=>setRolesText(e.target.value)}
              onBlur={commitRoles}
              className="mt-1 w-full rounded-lg border px-3 py-2"
            />
          </label>
        </div>

        <label className="block text-sm">
          <span className="text-zinc-700">Disqualifiers (comma-separated)</span>
          <input
            value={disqText}
            onChange={(e)=>setDisqText(e.target.value)}
            onBlur={commitDisq}
            className="mt-1 w-full rounded-lg border px-3 py-2"
          />
        </label>
        <p className="text-xs text-zinc-500 mt-1">We’ll stop early if any disqualifier is true.</p>
      </div>


      {/* Tone & footer */}
      <div className="rounded-xl border p-4 bg-white space-y-3">
        <h2 className="font-medium">Writing style</h2>
        <div className="grid sm:grid-cols-2 gap-3">
          <label className="block text-sm">
            <span className="text-zinc-700">Tone</span>
            <select
              value={form.tone?.style || "friendly"}
              onChange={(e) => set("tone.style", e.target.value)}
              className="mt-1 w-full rounded-lg border px-3 py-2"
            >
              <option value="friendly">Friendly</option>
              <option value="neutral">Neutral</option>
              <option value="formal">Formal</option>
            </select>
          </label>
          <label className="block text-sm">
            <span className="text-zinc-700">Length</span>
            <select
              value={form.tone?.length || "short"}
              onChange={(e) => set("tone.length", e.target.value)}
              className="mt-1 w-full rounded-lg border px-3 py-2"
            >
              <option value="short">Short</option>
              <option value="medium">Medium</option>
            </select>
          </label>
        </div>

        <label className="block text-sm">
          <span className="text-zinc-700">Outreach footer (optional)</span>
          <input
            value={form.outreach_footer || ""}
            onChange={(e) => set("outreach_footer", e.target.value)}
            className="mt-1 w-full rounded-lg border px-3 py-2"
          />
        </label>
      </div>

      {/* Save + feedback */}
      <div className="flex items-center gap-3">
        <button
          onClick={save}
          disabled={busy || !changed}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-white hover:bg-indigo-700 disabled:opacity-60"
        >
          {busy ? "Saving…" : changed ? "Save" : "Saved"}
        </button>
        {okMsg && <span className="text-sm text-emerald-700">{okMsg}</span>}
        {errMsg && <span className="text-sm text-rose-700">{errMsg}</span>}
        <a href="/app" className="ml-auto text-sm underline">Go to App</a>
      </div>
    </div>
  );
}
