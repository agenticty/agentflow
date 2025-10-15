"use client";
type Kind = "success" | "error" | "info";
export default function Alert({ title, body, kind = "info" }:{
  title: string; body?: string; kind?: Kind;
}) {
  const map = {
    success: "bg-emerald-50 text-emerald-800 border-emerald-200",
    error: "bg-rose-50 text-rose-800 border-rose-200",
    info: "bg-indigo-50 text-indigo-800 border-indigo-200",
  } as const;
  return (
    <div className={`border rounded-xl p-4 ${map[kind]}`}>
      <div className="font-medium">{title}</div>
      {body && <div className="text-sm mt-1/2">{body}</div>}
    </div>
  );
}
