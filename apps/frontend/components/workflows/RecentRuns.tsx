"use client";

import { useEffect, useState } from "react";
import { Skeleton } from "@/components/ui/Skeleton";

type RunItem = {
    id: string;
    workflow_id: string;
    workflow_name: string;
    company: string;
    status: string;
    started_at: string | null;
    finished_at: string | null;
};

function StatusBadge({ status }: { status: string }) {
    const map: Record<string, { label: string; className: string }> = {
        running: { label: "Running", className: "bg-blue-100 text-blue-700 border-blue-200" },
        success: { label: "Success", className: "bg-emerald-100 text-emerald-700 border-emerald-200" },
        stopped_low_quality: { label: "Low Quality", className: "bg-amber-100 text-amber-700 border-amber-200" },
        disqualified: { label: "Disqualified", className: "bg-orange-100 text-orange-700 border-orange-200" },
        error: { label: "Error", className: "bg-rose-100 text-rose-700 border-rose-200" },
    };

    const badge = map[status] || { label: status, className: "bg-zinc-100 text-zinc-700 border-zinc-200" };

    return (
        <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${badge.className}`}>
            {badge.label}
        </span>
    );
}

function timeAgo(isoString: string | null): string {
    if (!isoString) return "—";

    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return "just now";
    if (diffMins < 60) return `${diffMins}m ago`;

    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;

    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays}d ago`;
}

export default function RecentRuns({ onViewLogs }: { onViewLogs: (runId: string) => void }) {
    const [runs, setRuns] = useState<RunItem[] | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        (async () => {
            try {
                const base = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
                const r = await fetch(`${base}/api/workflow-runs/recent?limit=5`, { cache: "no-store" });
                if (!r.ok) throw new Error(`Failed to fetch runs (${r.status})`);
                const data = await r.json();
                setRuns(data);
            } catch (e: unknown) {
                setError(e instanceof Error ? e.message : "Unknown error");
            } finally {
                setLoading(false);
            }
        })();
    }, []);

    if (loading) {
        return (
            <div className="space-y-2">
                <Skeleton className="h-16" />
                <Skeleton className="h-16" />
                <Skeleton className="h-16" />
            </div>
        );
    }

    if (error) {
        return (
            <div className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
                Error loading runs: {error}
            </div>
        );
    }

    if (!runs || runs.length === 0) {
        return (
            <div className="rounded-lg border bg-zinc-50 p-6 text-center text-sm text-zinc-600">
                No runs yet. Run your first workflow to see history here.
            </div>
        );
    }

    return (
        <div className="space-y-2">
            {runs.map((run) => (
                <div
                    key={run.id}
                    className="rounded-lg border bg-white p-3 hover:shadow-sm transition cursor-pointer"
                    onClick={() => onViewLogs(run.id)}
                >
                    <div className="flex items-start justify-between gap-3">
                        <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                                <div className="font-medium text-sm truncate">
                                    {run.company}
                                </div>
                                <StatusBadge status={run.status} />
                            </div>
                            <div className="text-xs text-zinc-500 mt-0.5">
                                {run.workflow_name}
                            </div>
                        </div>
                        <div className="text-xs text-zinc-500 whitespace-nowrap">
                            {timeAgo(run.started_at)}
                        </div>
                    </div>
                </div>
            ))}
        </div>
    );
}