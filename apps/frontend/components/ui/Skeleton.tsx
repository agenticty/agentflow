export function Skeleton({ className = "" }: { className?: string }) {
    return <div className={`animate-pulse rounded-lg bg-zinc-200/70 ${className}`} />;
  }
  