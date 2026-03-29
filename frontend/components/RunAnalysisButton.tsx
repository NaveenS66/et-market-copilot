"use client";

import { useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const STEPS = [
  "Fetching market data…",
  "Detecting signals…",
  "Enriching context…",
  "Generating alerts…",
  "Saving results…",
];

interface RunAnalysisButtonProps {
  onComplete: () => void;
}

export default function RunAnalysisButton({ onComplete }: RunAnalysisButtonProps) {
  const [loading, setLoading] = useState(false);
  const [stepIndex, setStepIndex] = useState(0);
  const [error, setError] = useState<string | null>(null);

  async function handleClick() {
    setLoading(true);
    setError(null);
    setStepIndex(0);

    const interval = setInterval(() => {
      setStepIndex((prev: number) => Math.min(prev + 1, STEPS.length - 1));
    }, 3000);

    try {
      const res = await fetch(`${API_BASE}/api/analysis/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tickers: null, scenario: null }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `Error ${res.status}`);
      }

      const alerts = await res.json();
      if (Array.isArray(alerts) && alerts.length === 0) {
        setError("Pipeline ran — no signals detected for current holdings. Try adding INFY.NS or HDFCBANK.NS for richer signals.");
      }
      onComplete();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Analysis failed");
    } finally {
      clearInterval(interval);
      setLoading(false);
      setStepIndex(0);
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <button
        onClick={handleClick}
        disabled={loading}
        className="bg-indigo-600 text-white px-5 py-2.5 rounded-lg font-semibold text-sm hover:bg-indigo-700 disabled:opacity-60 transition-colors flex items-center gap-2"
      >
        {loading ? (
          <>
            <span className="inline-block w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
            Running…
          </>
        ) : (
          "Run Analysis"
        )}
      </button>

      {loading && (
        <div className="flex flex-col gap-1">
          <div className="w-full bg-gray-200 rounded-full h-1.5">
            <div
              className="bg-indigo-500 h-1.5 rounded-full transition-all duration-700"
              style={{ width: `${((stepIndex + 1) / STEPS.length) * 100}%` }}
            />
          </div>
          <p className="text-xs text-gray-500">{STEPS[stepIndex]}</p>
        </div>
      )}

      {error && <p className="text-sm text-red-600">{error}</p>}
    </div>
  );
}
