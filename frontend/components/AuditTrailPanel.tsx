"use client";

import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface AuditStep {
  id: string;
  alert_id: string;
  agent_name: string;
  action: string;
  source_urls: string[] | null;
  model_used: string | null;
  fallback_occurred: boolean;
  fallback_reason: string | null;
  output_summary: string | null;
  task_type: string | null;
  estimated_cost_saved: number | null;
  timestamp: string;
}

interface AuditTrailPanelProps {
  alertId: string;
  inlineSteps?: AuditStep[] | null;
  onClose: () => void;
}

const AGENT_COLORS: Record<string, string> = {
  DataFetcher: "bg-blue-100 text-blue-800",
  SignalDetector: "bg-purple-100 text-purple-800",
  ContextEnricher: "bg-teal-100 text-teal-800",
  AlertGenerator: "bg-orange-100 text-orange-800",
  ModelRouter: "bg-yellow-100 text-yellow-800",
  AuditLog: "bg-gray-100 text-gray-700",
};

function AgentChip({ name }: { name: string }) {
  const cls = AGENT_COLORS[name] || "bg-gray-100 text-gray-700";
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs font-semibold ${cls}`}>
      {name}
    </span>
  );
}

export default function AuditTrailPanel({ alertId, inlineSteps, onClose }: AuditTrailPanelProps) {
  const [steps, setSteps] = useState<AuditStep[]>(inlineSteps || []);
  const [loading, setLoading] = useState(!inlineSteps || inlineSteps.length === 0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // If we already have inline steps, no need to fetch
    if (inlineSteps && inlineSteps.length > 0) {
      setSteps(inlineSteps);
      setLoading(false);
      return;
    }
    fetch(`${API_BASE}/api/alerts/${alertId}/audit`)
      .then((r) => r.json())
      .then((data) => {
        setSteps(Array.isArray(data) ? data : []);
        setLoading(false);
      })
      .catch((e) => {
        setError(e.message);
        setLoading(false);
      });
  }, [alertId, inlineSteps]);

  const routerSteps = steps.filter((s: AuditStep) => s.agent_name === "ModelRouter");
  const otherSteps = steps.filter((s: AuditStep) => s.agent_name !== "ModelRouter");
  const totalSaved = routerSteps.reduce((acc: number, s: AuditStep) => acc + (s.estimated_cost_saved || 0), 0);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-2xl max-h-[85vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200">
          <h2 className="font-semibold text-gray-900">Agent Reasoning Trail</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-700 text-xl leading-none"
          >
            ✕
          </button>
        </div>

        {/* Body */}
        <div className="overflow-y-auto flex-1 px-5 py-4 space-y-4">
          {loading && <p className="text-sm text-gray-500">Loading audit trail…</p>}
          {error && <p className="text-sm text-red-600">{error}</p>}

          {/* Timeline steps */}
          {otherSteps.map((step, i) => (
            <div key={step.id || i} className="flex gap-3">
              <div className="flex flex-col items-center">
                <div className="w-2.5 h-2.5 rounded-full bg-blue-400 mt-1 shrink-0" />
                {i < otherSteps.length - 1 && (
                  <div className="w-px flex-1 bg-gray-200 mt-1" />
                )}
              </div>
              <div className="pb-4 flex-1 min-w-0">
                <div className="flex flex-wrap items-center gap-2 mb-1">
                  <AgentChip name={step.agent_name} />
                  <span className="text-xs font-medium text-gray-700">{step.action}</span>
                  {step.model_used && (
                    <span className="text-xs text-gray-500 bg-gray-100 px-1.5 py-0.5 rounded">
                      {step.model_used}
                    </span>
                  )}
                  {step.fallback_occurred && (
                    <span className="text-xs text-amber-700 bg-amber-100 px-1.5 py-0.5 rounded">
                      fallback
                    </span>
                  )}
                  <span className="text-xs text-gray-400 ml-auto">
                    {new Date(step.timestamp).toLocaleTimeString()}
                  </span>
                </div>
                {step.output_summary && (
                  <p className="text-xs text-gray-600 mb-1">{step.output_summary}</p>
                )}
                {step.fallback_reason && (
                  <p className="text-xs text-amber-700">Fallback reason: {step.fallback_reason}</p>
                )}
                {step.source_urls && step.source_urls.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-1">
                    {step.source_urls.map((url, j) => (
                      <a
                        key={j}
                        href={url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-blue-600 hover:underline truncate max-w-xs"
                      >
                        {url}
                      </a>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}

          {/* Model Routing section */}
          {routerSteps.length > 0 && (
            <div className="border border-yellow-200 rounded-lg p-3 bg-yellow-50">
              <p className="text-xs font-semibold text-yellow-800 mb-2">Model Routing</p>
              <ul className="space-y-1">
                {routerSteps.map((step, i) => (
                  <li key={step.id || i} className="text-xs text-yellow-900">
                    {step.output_summary}
                  </li>
                ))}
              </ul>
              {totalSaved > 0 && (
                <p className="text-xs font-semibold text-yellow-800 mt-2 border-t border-yellow-200 pt-2">
                  Total saved vs all-GPT-4o: ~${totalSaved.toFixed(4)}
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
