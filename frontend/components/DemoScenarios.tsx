"use client";

import { useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const SCENARIOS = [
  {
    id: "bulk_deal",
    label: "Scenario 1: Bulk Deal Signal",
    description: "Promoter sells 4.2% stake at 6% discount — distress or routine?",
    color: "bg-red-50 border-red-200 hover:bg-red-100",
    badge: "bg-red-100 text-red-800",
    badgeText: "BULK DEAL",
  },
  {
    id: "breakout",
    label: "Scenario 2: Conflicted Breakout",
    description: "52W high breakout + RSI 78 + FII reduction — bull or bear?",
    color: "bg-amber-50 border-amber-200 hover:bg-amber-100",
    badge: "bg-amber-100 text-amber-800",
    badgeText: "CONFLICTED",
  },
  {
    id: "macro",
    label: "Scenario 3: Dual Macro Events",
    description: "RBI rate cut + SEBI regulation hit portfolio simultaneously — which matters more?",
    color: "bg-blue-50 border-blue-200 hover:bg-blue-100",
    badge: "bg-blue-100 text-blue-800",
    badgeText: "MACRO",
  },
];

interface DemoScenariosProps {
  onAlertGenerated: (alert: unknown) => void;
}

export default function DemoScenarios({ onAlertGenerated }: DemoScenariosProps) {
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function runScenario(scenarioId: string) {
    setLoading(scenarioId);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/demo/${scenarioId}`, {
        method: "POST",
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `Error ${res.status}`);
      }
      const alert = await res.json();
      onAlertGenerated(alert);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Demo failed");
    } finally {
      setLoading(null);
    }
  }

  return (
    <div className="border border-gray-200 rounded-lg p-4 bg-white">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-sm font-semibold text-gray-700">Judge Scenario Pack</span>
        <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">3 required scenarios</span>
      </div>
      <p className="text-xs text-gray-500 mb-4">
        Pre-loaded with realistic NSE data. Each runs the full agent pipeline — signal detection → context enrichment → alert generation.
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {SCENARIOS.map((s) => (
          <button
            key={s.id}
            onClick={() => runScenario(s.id)}
            disabled={loading !== null}
            className={`text-left border rounded-lg p-3 transition-colors disabled:opacity-60 ${s.color}`}
          >
            <div className="flex items-center gap-2 mb-1.5">
              <span className={`text-xs font-semibold px-1.5 py-0.5 rounded ${s.badge}`}>
                {s.badgeText}
              </span>
              {loading === s.id && (
                <span className="inline-block w-3 h-3 border-2 border-gray-400 border-t-transparent rounded-full animate-spin" />
              )}
            </div>
            <p className="text-xs font-semibold text-gray-800 mb-1">{s.label}</p>
            <p className="text-xs text-gray-600">{s.description}</p>
          </button>
        ))}
      </div>
      {error && <p className="text-xs text-red-600 mt-2">{error}</p>}
    </div>
  );
}
