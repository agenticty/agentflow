"use client";
export default function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 text-zinc-600">
      <span className="size-4 animate-spin rounded-full border-[3px] border-zinc-300 border-t-indigo-600" />
      {label && <span className="text-sm">{label}</span>}
    </div>
  );
}
