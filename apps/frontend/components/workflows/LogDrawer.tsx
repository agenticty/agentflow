/* eslint-disable @typescript-eslint/no-explicit-any */
"use client";
import { useEffect, useRef, useState } from "react";
import EmailPreview from "./EmailPreview";

// ============================================================================
// HELPER COMPONENTS
// ============================================================================

function StopReasonCard({ data }: { data: any }) {
  const { reason, detail, recommendation, quality_score } = data;

  return (
    <div className="rounded-lg border-2 border-amber-300 bg-amber-50 p-4 space-y-2">
      <div className="flex items-start gap-2">
        <div className="mt-0.5">⚠️</div>
        <div className="flex-1">
          <div className="font-semibold text-amber-900">
            Run Stopped: {reason || "Quality check failed"}
          </div>

          {detail && (
            <div className="mt-2 text-sm text-amber-800">
              {detail}
            </div>
          )}

          {quality_score && (
            <div className="mt-3 rounded-md bg-white/60 p-3 text-xs space-y-1">
              <div className="font-medium text-amber-900">Quality Analysis:</div>
              <div className="text-amber-800">
                • Confidence: {quality_score.confidence}% ({quality_score.quality})
              </div>
              <div className="text-amber-800">
                • Credible sources: {quality_score.total_credible}/{quality_score.total_urls}
              </div>
              {quality_score.tier1_sources > 0 && (
                <div className="text-amber-800">
                  • Premium sources (Reuters, Bloomberg, etc.): {quality_score.tier1_sources}
                </div>
              )}
            </div>
          )}

          {recommendation && (
            <div className="mt-3 rounded-md bg-amber-100 px-3 py-2 text-sm">
              <span className="font-medium">💡 Recommendation:</span> {recommendation}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function QualityScoreCard({ data }: { data: any }) {
  const { confidence, quality, sources } = data;

  const colorMap: Record<string, string> = {
    high: "text-emerald-700 bg-emerald-50 border-emerald-200",
    good: "text-blue-700 bg-blue-50 border-blue-200",
    medium: "text-amber-700 bg-amber-50 border-amber-200",
    low: "text-orange-700 bg-orange-50 border-orange-200",
    insufficient: "text-rose-700 bg-rose-50 border-rose-200"
  };

  const colorClass = colorMap[quality] || colorMap.medium;

  return (
    <div className={`rounded-lg border px-3 py-2 text-sm ${colorClass}`}>
      <div className="font-medium">
        Research Quality: {quality.toUpperCase()} ({confidence}% confidence)
      </div>
      {sources && (
        <div className="mt-1 text-xs opacity-90">
          Found {sources.total_credible} credible sources ({sources.tier1} premium) from {sources.total_found} checked
        </div>
      )}
    </div>
  );
}

function QualificationCard({ data }: { data: any }) {
  const { score, decision, confidence, criteria_matched, total_criteria } = data;

  const colorMap: Record<string, string> = {
    yes: "text-emerald-700 bg-emerald-50 border-emerald-200",
    maybe: "text-amber-700 bg-amber-50 border-amber-200",
    no: "text-rose-700 bg-rose-50 border-rose-200"
  };

  const colorClass = colorMap[decision] || colorMap.maybe;

  return (
    <div className={`rounded-lg border px-3 py-2 text-sm ${colorClass}`}>
      <div className="font-medium">
        Qualification: {decision.toUpperCase()} (Score: {score}/100)
      </div>
      <div className="text-xs opacity-90 mt-1">
        {confidence} confidence • Matched {criteria_matched}/{total_criteria} ICP criteria
      </div>
    </div>
  );
}

function EmailQualityIndicator({ email }: { email: string }) {
  const wordCount = email.split(/\s+/).filter(w => w.length > 0).length;
  const hasQuestion = /\?/.test(email);
  const hasForbidden = /(hope this finds you well|strategic partnership|enhance your|thought leadership|reaching out to discuss)/i.test(email);

  const checks = [
    {
      label: "Length (60-90 words)",
      pass: wordCount >= 50 && wordCount <= 100,
      current: `${wordCount} words`,
      importance: "critical"
    },
    
    {
      label: "Clear CTA question",
      pass: hasQuestion,
      current: hasQuestion ? "✓" : "✗",
      importance: "important"
    },
    {
      label: "No forbidden phrases",
      pass: !hasForbidden,
      current: hasForbidden ? "✗ Found" : "✓",
      importance: "important"
    }
  ];

  const criticalPassed = checks.filter(c => c.importance === "critical" && c.pass).length;
  const totalPassed = checks.filter(c => c.pass).length;

  let quality: string;
  let colorClass: string;

  if (criticalPassed === 1 && totalPassed === 3) {
    quality = "Excellent SDR email";
    colorClass = "text-emerald-700 border-emerald-200 bg-emerald-50";
  } else if (criticalPassed === 1 && totalPassed >= 2) {
    quality = "Good - minor improvements possible";
    colorClass = "text-blue-700 border-blue-200 bg-blue-50";
  } else if (criticalPassed >= 1) {
    quality = "Fair - needs improvements";
    colorClass = "text-amber-700 border-amber-200 bg-amber-50";
  } else {
    quality = "Needs work - missing critical elements";
    colorClass = "text-rose-700 border-rose-200 bg-rose-50";
  }

  return (
    <div className={`mt-3 rounded-lg border p-3 text-xs space-y-2 ${colorClass}`}>
      <div className="flex items-center justify-between">
        <span className="font-medium">Email Quality Check</span>
        <span className="font-semibold">{quality}</span>
      </div>
      <div className="space-y-1">
        {checks.map((check, i) => (
          <div key={i} className="flex items-center justify-between opacity-90">
            <span className={check.pass ? "" : "opacity-70"}>
              {check.pass ? "✓" : "○"} {check.label}
            </span>
            <span className="font-mono">{check.current}</span>
          </div>
        ))}
      </div>
      {totalPassed < 4 && (
        <div className="pt-2 border-t border-current/20 text-xs opacity-80">
          💡 Tip: Review the SDR email rules in Settings to improve quality
        </div>
      )}
    </div>
  );
}

// ============================================================================
// MAIN COMPONENT
// ============================================================================

type LogEvent = {
  ts: string;
  event: string;
  data: any;
};

type Line = {
  id: string;
  text: string;
  kind: "info" | "success" | "error";
  event?: LogEvent; // Store full event for rich rendering
};

function humanize(evt: LogEvent): Line {
  const e = evt?.event;
  const d = evt?.data || {};
  const ts = evt?.ts ? new Date(evt.ts).toLocaleTimeString() : "";
  const id = `${evt?.ts || Date.now()}-${Math.random().toString(36).slice(2, 7)}`;

  const mk = (text: string, kind: Line["kind"] = "info"): Line => ({
    id,
    text: ts ? `[${ts}] ${text}` : text,
    kind,
    event: evt, // Preserve full event
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

  if (e === "step:end") {
    return mk(`Step ${d.index} completed`, "success");
  }

  if (e === "research:quality") {
    return mk(
      `Research quality: ${d.quality} (${d.confidence}% confidence)`,
      d.confidence >= 75 ? "success" : d.confidence >= 50 ? "info" : "error"
    );
  }

  if (e === "qualify:assessed") {
    return mk(
      `Qualification: ${d.decision.toUpperCase()} (${d.score}/100)`,
      d.decision === "yes" ? "success" : d.decision === "no" ? "error" : "info"
    );
  }

  if (e === "finished") {
    if (d.reason) {
      return mk(`Run stopped: ${d.reason}`, "error");
    }
    return d.status === "stopped"
      ? mk("Run stopped (not enough evidence or disqualified).", "error")
      : mk("Autopilot finished successfully.", "success");
  }

  if (e === "error") return mk(`Error: ${d.message}`, "error");

  // Default fallback
  return mk(`${e || "message"}: ${JSON.stringify(d)}`, "info");
}

export default function LogDrawer({
  runId,
  onClose
}: {
  runId: string;
  onClose: () => void
}) {
  const [lines, setLines] = useState<Line[]>([]);
  const [outreachText, setOutreachText] = useState<string | null>(null);
  const [contactEmail, setContactEmail] = useState<string>("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const base = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
    const es = new EventSource(`${base}/api/workflow-runs/${runId}/logs`);

    es.onmessage = (ev) => {
      try {
        const parsed: LogEvent = JSON.parse(ev.data);
        const { event, data } = parsed || {};

        // Capture outreach email
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
      setLines((prev) => [...prev, {
        id,
        text: "Connection lost. Reconnecting…",
        kind: "error"
      }]);
    };

    // Also fetch run details to get contact email
    (async () => {
      try {
        const r = await fetch(`${base}/api/workflow-runs/${runId}`);
        if (r.ok) {
          const run = await r.json();
          setContactEmail(run?.inputs?.lead_email || "");
        }
      } catch {
        // Silently fail - email preview will work without "to" field
      }
    })();

    return () => es.close();
  }, [runId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [lines]);

  return (
    <div className="fixed inset-0 bg-black/30 z-50" onClick={onClose}>
      <div
        className="absolute right-0 top-0 h-full w-[600px] bg-white shadow-xl border-l flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b">
          <h3 className="font-semibold">Live Run Logs</h3>
          <button
            onClick={onClose}
            className="rounded-md border px-3 py-1.5 text-sm hover:bg-zinc-50"
          >
            Close
          </button>
        </div>

        {/* Email Preview (if exists) */}
        {outreachText && (
          <div className="p-4 border-b bg-zinc-50">
            <EmailPreview text={outreachText} to={contactEmail} />
            <EmailQualityIndicator email={outreachText} />
          </div>
        )}

        {/* Log Stream */}
        <div className="flex-1 overflow-auto p-4">
          <div className="space-y-3">
            {lines.length === 0 ? (
              <div className="text-center text-zinc-500 py-8">
                <div className="animate-pulse">Connecting to live logs…</div>
              </div>
            ) : (
              lines.map((line) => {
                // Rich rendering for special events
                if (line.event?.event === "research:quality") {
                  return (
                    <div key={line.id} className="space-y-2">
                      <div className="text-xs text-zinc-500 font-mono">{line.text}</div>
                      <QualityScoreCard data={line.event.data} />
                    </div>
                  );
                }

                if (line.event?.event === "qualify:assessed") {
                  return (
                    <div key={line.id} className="space-y-2">
                      <div className="text-xs text-zinc-500 font-mono">{line.text}</div>
                      <QualificationCard data={line.event.data} />
                    </div>
                  );
                }

                if (line.event?.event === "finished" && line.event.data?.reason) {
                  return (
                    <div key={line.id} className="space-y-2">
                      <div className="text-xs text-zinc-500 font-mono">{line.text}</div>
                      <StopReasonCard data={line.event.data} />
                    </div>
                  );
                }

                // Default text rendering
                return (
                  <div
                    key={line.id}
                    className={`text-xs font-mono whitespace-pre-wrap ${line.kind === "success"
                        ? "text-emerald-700"
                        : line.kind === "error"
                          ? "text-rose-700"
                          : "text-zinc-700"
                      }`}
                  >
                    {line.text}
                  </div>
                );
              })
            )}
            <div ref={bottomRef} />
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 border-t bg-zinc-50 flex items-center justify-between">
          <div className="text-xs text-zinc-500">
            💡 Watch research → qualify → outreach in real-time
          </div>
          <button
            onClick={() => {
              const text = lines.map((x) => x.text).join("\n");
              navigator.clipboard?.writeText(text);
            }}
            className="rounded-md border px-3 py-1.5 text-xs hover:bg-white"
          >
            📋 Copy all logs
          </button>
        </div>
      </div>
    </div>
  );
}