"use client";

import { useCallback, useEffect, useState } from "react";
import AddHoldingForm from "@/components/AddHoldingForm";
import AlertCard, { Alert } from "@/components/AlertCard";
import DemoScenarios from "@/components/DemoScenarios";
import PortfolioTable from "@/components/PortfolioTable";
import RunAnalysisButton from "@/components/RunAnalysisButton";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Holding {
  id: string;
  ticker: string;
  quantity: number;
  avg_buy_price: number;
  current_price: number;
  day_change_pct: number;
  unrealised_pnl: number;
  created_at: string;
}

export default function Home() {
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [portfolioLoading, setPortfolioLoading] = useState(true);
  const [alertsLoading, setAlertsLoading] = useState(true);

  const fetchPortfolio = useCallback(async () => {
    setPortfolioLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/portfolio`);
      const data = await res.json();
      setHoldings(Array.isArray(data) ? data : []);
    } catch {
      // silently fail — user will see empty state
    } finally {
      setPortfolioLoading(false);
    }
  }, []);

  const fetchAlerts = useCallback(async () => {
    setAlertsLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/alerts`);
      const data = await res.json();
      // Only show the most recent run — dedupe by ticker, keep latest
      const seen = new Set<string>();
      const deduped = (Array.isArray(data) ? data : []).filter((a: Alert) => {
        if (seen.has(a.ticker)) return false;
        seen.add(a.ticker);
        return true;
      });
      setAlerts(deduped);
    } catch {
      // silently fail
    } finally {
      setAlertsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPortfolio();
    fetchAlerts();
  }, [fetchPortfolio, fetchAlerts]);

  async function handleDelete(ticker: string) {
    try {
      await fetch(`${API_BASE}/api/portfolio/holding/${ticker}`, { method: "DELETE" });
      fetchPortfolio();
    } catch {
      // ignore
    }
  }

  return (
    <div className="container mx-auto px-4 py-8 max-w-5xl">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">ET Investor Copilot</h1>
        <p className="text-gray-500 text-sm">Portfolio-aware signal intelligence for Indian retail investors</p>
      </div>

      {/* Portfolio section */}
      <section className="mb-10">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold text-gray-800">My Portfolio</h2>
          {portfolioLoading && <span className="text-xs text-gray-400">Loading…</span>}
        </div>
        <PortfolioTable holdings={holdings} onDelete={handleDelete} />
        <AddHoldingForm onAdded={fetchPortfolio} />
      </section>

      {/* Run Analysis + Alerts section */}
      <section className="mb-10">
        <div className="flex items-center gap-4 flex-wrap mb-4">
          <RunAnalysisButton onComplete={fetchAlerts} />
          <p className="text-xs text-gray-400">
            Runs the full agent pipeline for all holdings in your portfolio.
          </p>
        </div>

        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold text-gray-800">Signal Alerts</h2>
          {alertsLoading && <span className="text-xs text-gray-400">Loading…</span>}
        </div>

        {!alertsLoading && alerts.length === 0 && (
          <p className="text-gray-500 text-sm py-4">
            No alerts yet. Add holdings above and click Run Analysis.
          </p>
        )}

        <div className="space-y-3">
          {alerts.map((alert: Alert) => (
            <AlertCard key={alert.alert_id} alert={alert} />
          ))}
        </div>
      </section>

      {/* Demo Scenarios — at bottom for judge evaluation */}
      <section className="mb-10">
        <div className="flex items-center gap-2 mb-3">
          <h2 className="text-lg font-semibold text-gray-800">Judge Scenario Pack</h2>
          <span className="text-xs bg-indigo-100 text-indigo-700 px-2 py-0.5 rounded font-medium">Demo Only</span>
        </div>
        <p className="text-xs text-gray-500 mb-3">
          Pre-loaded NSE scenarios for hackathon evaluation. Each runs the full agent pipeline independently.
        </p>
        <DemoScenarios onAlertGenerated={(alert) => {
          setAlerts((prev: Alert[]) => {
            const incoming: Alert[] = Array.isArray(alert) ? alert as Alert[] : [alert as Alert];
            const filtered = prev.filter((x: Alert) => !incoming.some((a) => a.ticker === x.ticker));
            return [...incoming, ...filtered];
          });
        }} />
      </section>
    </div>
  );
}
