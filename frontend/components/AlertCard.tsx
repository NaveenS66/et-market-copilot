"use client";

import { useState } from "react";
import AuditTrailPanel from "./AuditTrailPanel";

interface EvidenceItem {
  label: string;
  value: string;
  source_name: string;
  source_url: string;
  retrieved_at: string;
}

export interface Alert {
  alert_id: string;
  id?: string;
  ticker: string;
  signal_type: string;
  summary: string;
  recommended_action: string;
  confidence: string;
  estimated_impact_inr_low: number | null;
  estimated_impact_inr_high: number | null;
  evidence_chain: EvidenceItem[];
  bull_case: string | null;
  bear_case: string | null;
  what_to_watch: string[] | null;
  disclaimer: string;
  personalized_opening: string | null;
  holding_duration_days: number | null;
  unrealised_pnl_inr: number | null;
  impact_pct_of_portfolio: number | null;
  unreported_signal: boolean;
  created_at: string;
}

interface AlertCardProps {
  alert: Alert;
}

function SignalBadge({ type }: { type: string }) {
  const styles: Record<string, string> = {
    bulk_deal: "bg-red-100 text-red-800",
    breakout_conflicted: "bg-amber-100 text-amber-800",
    macro_event: "bg-blue-100 text-blue-800",
    breakout: "bg-green-100 text-green-800",
  };
  const labels: Record<string, string> = {
    bulk_deal: "BULK DEAL",
    breakout_conflicted: "CONFLICTED",
    macro_event: "MACRO",
    breakout: "BREAKOUT",
  };
  const cls = styles[type] || "bg-gray-100 text-gray-800";
  const label = labels[type] || type.toUpperCase();
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs font-semibold ${cls}`}>
      {label}
    </span>
  );
}

function ConfidenceBadge({ confidence }: { confidence: string }) {
  const styles: Record<string, string> = {
    High: "bg-green-100 text-green-800",
    Medium: "bg-yellow-100 text-yellow-800",
    Low: "bg-gray-100 text-gray-700",
  };
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${styles[confidence] || "bg-gray-100 text-gray-700"}`}>
      {confidence} confidence
    </span>
  );
}

function fmt(n: number) {
  return n.toLocaleString("en-IN", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

export default function AlertCard({ alert }: AlertCardProps) {
  const [expanded, setExpanded] = useState(false);
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [auditOpen, setAuditOpen] = useState(false);

  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden">
      {/* Header row */}
      <div
        className="flex items-start gap-3 px-4 py-3 cursor-pointer hover:bg-gray-50 transition-colors"
        onClick={() => setExpanded((v: boolean) => !v)}
      >
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2 mb-1">
            <SignalBadge type={alert.signal_type} />
            {alert.unreported_signal && (
              <span className="inline-block px-2 py-0.5 rounded text-xs font-semibold bg-amber-100 text-amber-800">
                🔍 Unreported Signal
              </span>
            )}
            <span className="font-bold text-gray-900">{alert.ticker}</span>
            <ConfidenceBadge confidence={alert.confidence} />
          </div>
          <p className="text-sm text-gray-700 line-clamp-2">{alert.summary}</p>
        </div>
        <span className="text-gray-400 text-sm mt-0.5">{expanded ? "▲" : "▼"}</span>
      </div>

      {/* Expanded content */}
      {expanded && (
        <div className="border-t border-gray-100 px-4 py-4 space-y-4">
          {/* Personalized opening */}
          {alert.personalized_opening && (
            <div className="bg-blue-50 border border-blue-200 rounded px-3 py-2 text-sm text-blue-800 italic">
              {alert.personalized_opening}
            </div>
          )}

          {/* Recommended action */}
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase mb-1">Recommended Action</p>
            <p className="text-sm text-gray-800">{alert.recommended_action}</p>
          </div>

          {/* Impact range */}
          {alert.estimated_impact_inr_low !== null && alert.estimated_impact_inr_high !== null && (
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase mb-1">Estimated Impact</p>
              <p className="text-sm font-medium text-gray-800">
                ₹{fmt(alert.estimated_impact_inr_low)} to ₹{fmt(alert.estimated_impact_inr_high)}
              </p>
              {alert.impact_pct_of_portfolio !== null && (
                <p className="text-xs text-gray-500 mt-0.5">
                  Impact: {alert.impact_pct_of_portfolio?.toFixed(1)}% of total portfolio
                </p>
              )}
            </div>
          )}

          {/* Bull / Bear case */}
          {(alert.bull_case || alert.bear_case) && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {alert.bull_case && (
                <div className="bg-green-50 border border-green-200 rounded p-3">
                  <p className="text-xs font-semibold text-green-700 mb-1">Bull Case</p>
                  <p className="text-sm text-green-900">{alert.bull_case}</p>
                </div>
              )}
              {alert.bear_case && (
                <div className="bg-red-50 border border-red-200 rounded p-3">
                  <p className="text-xs font-semibold text-red-700 mb-1">Bear Case</p>
                  <p className="text-sm text-red-900">{alert.bear_case}</p>
                </div>
              )}
            </div>
          )}

          {/* What to watch */}
          {alert.what_to_watch && alert.what_to_watch.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase mb-1">What to Watch</p>
              <ul className="list-disc list-inside space-y-1">
                {alert.what_to_watch.map((item, i) => (
                  <li key={i} className="text-sm text-gray-700">{item}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Evidence chain */}
          {alert.evidence_chain && alert.evidence_chain.length > 0 && (
            <div>
              <button
                onClick={() => setEvidenceOpen((v: boolean) => !v)}
                className="text-xs font-semibold text-blue-600 hover:text-blue-800 flex items-center gap-1"
              >
                {evidenceOpen ? "▼" : "▶"} Evidence Chain ({alert.evidence_chain.length} sources)
              </button>
              {evidenceOpen && (
                <ul className="mt-2 space-y-1 pl-2 border-l-2 border-blue-100">
                  {alert.evidence_chain.map((ev, i) => (
                    <li key={i} className="text-xs text-gray-600">
                      <span className="font-medium">{ev.label}:</span> {ev.value} —{" "}
                      <a
                        href={ev.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-600 hover:underline"
                      >
                        {ev.source_name}
                      </a>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {/* Show Reasoning button */}
          <div className="flex items-center gap-3 pt-1">
            <button
              onClick={() => setAuditOpen(true)}
              className="text-sm text-gray-600 hover:text-gray-900 border border-gray-300 rounded px-3 py-1.5 hover:bg-gray-50 transition-colors"
            >
              Show Reasoning
            </button>
            <p className="text-xs text-gray-400 italic">{alert.disclaimer}</p>
          </div>
        </div>
      )}

      {/* Audit trail modal */}
      {auditOpen && (
        <AuditTrailPanel alertId={alert.alert_id || (alert as any).id} onClose={() => setAuditOpen(false)} />
      )}
    </div>
  );
}
