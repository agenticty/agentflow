/*setupgate.tsx */
"use client";
import { useEffect, useState } from "react";

type Org = {
  name?: string;
  product_one_liner?: string;
  value_props?: string[];
  icp?: { industries?: string[]; roles?: string[] };
};

export default function SetupGate({ children }:{ children: (configured: boolean)=>React.ReactNode }) {
  const [configured, setConfigured] = useState(false);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const base = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
        const r = await fetch(`${base}/api/org/profile?t=${Date.now()}`, { cache: "no-store" });
        const org: Org = r.ok ? await r.json() : {};
        const ok =
          !!org?.name &&
          !!org?.product_one_liner &&
          Array.isArray(org?.value_props) && org.value_props.length > 0 &&
          (((org.icp?.industries?.length || 0) + (org.icp?.roles?.length || 0)) >= 2);
        setConfigured(ok);
      } catch {
        setConfigured(false);
      } finally {
        setLoaded(true);
      }
    })();
  }, []);

  if (!loaded) return null;

  return (
    <>
      {!configured && (
        <div className="mb-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-amber-800">
          Autopilot setup needed. Fill <a className="underline" href="/settings">Settings</a> so we can qualify leads and write in your voice.
        </div>
      )}
      {children(configured)}
    </>
  );
}
