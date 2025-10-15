"use client";

import WorkflowList from "@/components/workflows/WorkflowList";
import CreateWorkflowForm from "@/components/workflows/CreateWorkflowForm";
import SetupGate from "@/components/app/SetupGate";
import { useState } from "react";


export default function AppPage() {
  const [showAdvanced, setShowAdvanced] = useState(false);
  
  return (
    <SetupGate>
      {(configured) => (
        <div className="grid gap-8 lg:grid-cols-[1fr,420px]">
          <section>
            <header className="mb-4">
              <h1 className="text-2xl font-semibold tracking-tight">
              Research-Qualify-Outreach Workflow
              </h1>
              <p className="text-sm text-zinc-600">
              Give us a company and contact. Our AI employees research them, check if they&apos;re a fit, and draft a personalized email. 
              </p>
            </header>
            <WorkflowList configured={configured} />
          </section>

          <aside className="space-y-4">
            {/* Advanced toggle */}
            <button
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="w-full rounded-lg border px-3 py-2 text-sm text-zinc-600 hover:bg-zinc-50 flex items-center justify-between"
            >
              <span>Advanced: Custom Workflows</span>
              <svg 
                className={`w-4 h-4 transition-transform ${showAdvanced ? 'rotate-180' : ''}`}
                fill="none" 
                stroke="currentColor" 
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            {/* Show custom workflow form when toggled */}
            {showAdvanced && <CreateWorkflowForm />}

            {/* Tips card */}
            <div className="rounded-xl border bg-white p-4">
              <h3 className="font-medium">Tips</h3>
              <ul className="mt-2 list-disc pl-5 text-sm text-zinc-600">
                <li>Use the template to get started fast.</li>
                <li>Tweak Settings to match your ICP and voice.</li>
                {showAdvanced && (
                  <li>Custom workflows let you add/remove steps.</li>
                )}
              </ul>
            </div>
          </aside>
        </div>
      )}
    </SetupGate>
  );
}
