/*EmailPreview.tsx */
"use client";
import { useState } from "react";

function parseEmail(text: string) {
  // Expect "Subject: ..." then a blank line, then body; fallback: first line as subject.
  const m = text.match(/^\s*Subject:\s*(.+)\s*\n\s*\n([\s\S]*)$/i);
  if (m) return { subject: m[1].trim(), body: m[2].trim() };
  const [first, ...rest] = text.split("\n");
  return { subject: (first || "Draft outreach"), body: rest.join("\n").trim() };
}

export default function EmailPreview({ text, to }: { text: string; to?: string }) {
  const { subject, body } = parseEmail(text);
  const [copied, setCopied] = useState<"s"|"b"|"all"|null>(null);

  const wordCount = body.split(/\s+/).filter(w => w.length > 0).length;
  const isGoodLength = wordCount >= 50 && wordCount <= 100;

  async function copy(t: string, which: "s"|"b"|"all") {
    try { await navigator.clipboard.writeText(t); setCopied(which); setTimeout(()=>setCopied(null), 1500); } catch {}
  }

  const mailto = (() => {
    const qs = new URLSearchParams({ subject, body }).toString();
    return `mailto:${encodeURIComponent(to || "")}?${qs}`;
  })();

  return (
    <div className="rounded-2xl border bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-xs text-zinc-500">Email preview</div>
          {to ? <div className="text-sm text-zinc-700 mt-0.5">To: {to}</div> : null}
        </div>
        <div className="flex gap-2">
          <button onClick={()=>copy(subject,"s")} className="rounded-md border px-2 py-1 text-xs hover:bg-zinc-50">
            {copied==="s" ? "Copied ✓" : "Copy subject"}
          </button>
          <button onClick={()=>copy(body,"b")} className="rounded-md border px-2 py-1 text-xs hover:bg-zinc-50">
            {copied==="b" ? "Copied ✓" : "Copy body"}
          </button>
          <button onClick={()=>copy(`Subject: ${subject}\n\n${body}`,"all")} className="rounded-md border px-2 py-1 text-xs hover:bg-zinc-50">
            {copied==="all" ? "Copied ✓" : "Copy all"}
          </button>
          <a href={mailto} className="rounded-md bg-indigo-600 px-2 py-1 text-xs text-white hover:bg-indigo-700">
            Open in email
          </a>
        </div>
      </div>
      <div className="mt-3">
        <div className="text-sm font-medium">Subject</div>
        <div className="mt-1 rounded-lg border bg-zinc-50 px-3 py-2 text-sm">{subject}</div>
      </div>
      <div className="mt-3">
        <div className="flex items-center justify-between">
          <div className="text-sm font-medium">Body</div>
          <div className={`text-xs ${isGoodLength ? "text-emerald-600" : "text-amber-600"}`}>
            {wordCount} words {isGoodLength ? "✓" : "(aim for 60-90)"}
          </div>
        </div>
        <pre className="mt-1 rounded-lg border bg-zinc-50 px-3 py-2 text-sm whitespace-pre-wrap">
          {body}
        </pre>
      </div>
    </div>
  );
}
