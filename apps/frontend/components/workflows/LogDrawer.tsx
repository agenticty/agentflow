"use client";
import { useEffect, useRef, useState } from "react";
import EmailPreview from "./EmailPreview";

type Line = { id: string; text: string; kind: "info" | "success" | "error" };

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function humanize(evt: any): Line {
  const e = evt?.event;
  const d = evt?.data || {};
  const ts = evt?.ts ? new Date(evt.ts).toLocaleTimeString() : "";
  const id = `${evt?.ts || Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
  const mk = (text: string, kind: Line["kind"] = "info"): Line => ({
    id,
    text: ts ? `[${ts}] ${text}` : text,
    kind,
  });
  if (e === "started") return mk(`Autopilot started: ${d.workflow}`, "info");
  if (e === "step:start") {
    const label: Record<string, string> = {
      research: "Researching the company",
      qualify: "Checking fit (ICP)",
      outreach: "Drafting the email",
    };
    return mk(`Step ${d.index}: ${label[d.agent] ?? d.agent}…`, "info");
  }
  if (e === "step:output") {
    const preview = String(d.preview || "");
    const short = preview.length > 180 ? preview.slice(0, 180) + "…" : preview;
    return mk(`Step ${d.index} result: ${short}`, "info");
  }
  if (e === "finished") {
    return d.status === "stopped"
      ? mk("Run stopped (not enough evidence or disqualified).", "error")
      : mk("Autopilot finished successfully.", "success");
  }
  if (e === "error") return mk(`Error: ${d.message}`, "error");
  return mk(`${e || "message"}: ${JSON.stringify(d)}`, "info");
}

export default function LogDrawer({ runId, onClose }: { runId: string; onClose: () => void }) {
  const [lines, setLines] = useState<Line[]>([]);
  const [outreachText, setOutreachText] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const base = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
    const es = new EventSource(`${base}/api/workflow-runs/${runId}/logs`);

    es.onmessage = (ev) => {
      try {
        const parsed = JSON.parse(ev.data);
        const { event, data } = parsed || {};
        if (event === "step:output" && data?.agent === "outreach") {
          setOutreachText(data?.full || data?.preview || "");
        }
        setLines((prev) => [...prev, humanize(parsed)]);
      } catch {
        const id = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
        setLines((prev) => [...prev, { id, text: ev.data, kind: "info" }]);
      }
    };

    es.onerror = () => {
      const id = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
      setLines((prev) => [...prev, { id, text: "Connection lost. Reconnecting…", kind: "error" }]);
      // EventSource will auto-retry.
    };

    return () => es.close();
  }, [runId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [lines]);

  return (
    <div className="fixed inset-0 bg-black/30 z-50" onClick={onClose}>
      <div
        className="absolute right-0 top-0 h-full w-[520px] bg-white shadow-xl border-l p-4 flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <h3 className="font-semibold">Run Logs</h3>
          <button onClick={onClose} className="rounded-md border px-2 py-1 text-sm hover:bg-zinc-50">
            Close
          </button>
        </div>

        {outreachText && (
          <div className="mt-3">
            <EmailPreview text={outreachText} />
          </div>
        )}

        <div className="mt-3 flex-1 overflow-auto rounded-lg border bg-zinc-50 p-3 text-xs font-mono leading-relaxed">
          {lines.length === 0 ? (
            <div className="text-zinc-500">Connecting to live logs…</div>
          ) : (
            lines.map((l) => (
              <div
                key={l.id}
                className={`whitespace-pre-wrap ${
                  l.kind === "success" ? "text-emerald-700" : l.kind === "error" ? "text-rose-700" : "text-zinc-800"
                }`}
              >
                {l.text}
              </div>
            ))
          )}
          <div ref={bottomRef} />
        </div>

        <div className="mt-3 flex items-center justify-between">
          <div className="text-xs text-zinc-500">Tips: Keep this open to watch research → qualify → outreach.</div>
          <button
            onClick={() => navigator.clipboard?.writeText(lines.map((x) => x.text).join("\n"))}
            className="rounded-md border px-2 py-1 text-xs hover:bg-zinc-50"
          >
            Copy logs
          </button>
        </div>
      </div>
    </div>
  );
}
