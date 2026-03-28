"use client";

import { useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface AddHoldingFormProps {
  onAdded: () => void;
}

export default function AddHoldingForm({ onAdded }: AddHoldingFormProps) {
  const [ticker, setTicker] = useState("");
  const [quantity, setQuantity] = useState("");
  const [avgBuyPrice, setAvgBuyPrice] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE}/api/portfolio/holding`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ticker: ticker.trim().toUpperCase(),
          quantity: parseFloat(quantity),
          avg_buy_price: parseFloat(avgBuyPrice),
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `Error ${res.status}`);
      }

      setTicker("");
      setQuantity("");
      setAvgBuyPrice("");
      onAdded();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to add holding");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-wrap gap-3 items-end mt-4">
      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-gray-600">Ticker</label>
        <input
          type="text"
          placeholder="e.g. INFY.NS"
          value={ticker}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => setTicker(e.target.value)}
          required
          className="border border-gray-300 rounded px-3 py-2 text-sm w-32 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-gray-600">Quantity</label>
        <input
          type="number"
          placeholder="100"
          value={quantity}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => setQuantity(e.target.value)}
          required
          min="0.01"
          step="any"
          className="border border-gray-300 rounded px-3 py-2 text-sm w-28 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-gray-600">Avg Buy Price (₹)</label>
        <input
          type="number"
          placeholder="1450.00"
          value={avgBuyPrice}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => setAvgBuyPrice(e.target.value)}
          required
          min="0.01"
          step="any"
          className="border border-gray-300 rounded px-3 py-2 text-sm w-36 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>
      <button
        type="submit"
        disabled={loading}
        className="bg-blue-600 text-white px-4 py-2 rounded text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
      >
        {loading ? "Adding…" : "Add Holding"}
      </button>
      {error && (
        <p className="w-full text-red-600 text-sm mt-1">{error}</p>
      )}
    </form>
  );
}
