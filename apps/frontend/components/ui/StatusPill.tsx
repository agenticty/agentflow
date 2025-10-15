export default function StatusPill({ ok }: { ok: boolean }) {
    return ok ? (
      <span className="inline-flex items-center gap-2 rounded-full bg-emerald-50 px-3 py-1 text-emerald-700 text-xs border border-emerald-200">
        <span className="size-1.5 rounded-full bg-emerald-500" /> Ready to run
      </span>
    ) : (
      <span className="inline-flex items-center gap-2 rounded-full bg-amber-50 px-3 py-1 text-amber-700 text-xs border border-amber-200">
        <span className="size-1.5 rounded-full bg-amber-500" /> Setup needed
      </span>
    );
  }
  