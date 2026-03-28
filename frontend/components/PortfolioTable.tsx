"use client";

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

interface PortfolioTableProps {
  holdings: Holding[];
  onDelete: (ticker: string) => void;
}

function fmt(n: number, decimals = 2) {
  return n.toLocaleString("en-IN", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

export default function PortfolioTable({ holdings, onDelete }: PortfolioTableProps) {
  if (holdings.length === 0) {
    return (
      <p className="text-gray-500 text-sm py-4">
        No holdings yet. Add your first stock below.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200">
      <table className="min-w-full text-sm">
        <thead className="bg-gray-50 text-gray-600 uppercase text-xs">
          <tr>
            <th className="px-4 py-3 text-left">Ticker</th>
            <th className="px-4 py-3 text-right">Qty</th>
            <th className="px-4 py-3 text-right">Avg Buy (₹)</th>
            <th className="px-4 py-3 text-right">Current (₹)</th>
            <th className="px-4 py-3 text-right">Day Change %</th>
            <th className="px-4 py-3 text-right">Unrealised P&amp;L (₹)</th>
            <th className="px-4 py-3 text-center">Action</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100 bg-white">
          {holdings.map((h) => {
            const pnlPositive = h.unrealised_pnl >= 0;
            const dayPositive = h.day_change_pct >= 0;
            return (
              <tr key={h.ticker} className="hover:bg-gray-50 transition-colors">
                <td className="px-4 py-3 font-semibold text-gray-900">{h.ticker}</td>
                <td className="px-4 py-3 text-right text-gray-700">{fmt(h.quantity, 0)}</td>
                <td className="px-4 py-3 text-right text-gray-700">₹{fmt(h.avg_buy_price)}</td>
                <td className="px-4 py-3 text-right text-gray-700">₹{fmt(h.current_price)}</td>
                <td className={`px-4 py-3 text-right font-medium ${dayPositive ? "text-green-600" : "text-red-600"}`}>
                  {dayPositive ? "+" : ""}{fmt(h.day_change_pct)}%
                </td>
                <td className={`px-4 py-3 text-right font-medium ${pnlPositive ? "text-green-600" : "text-red-600"}`}>
                  {pnlPositive ? "+" : ""}₹{fmt(h.unrealised_pnl)}
                </td>
                <td className="px-4 py-3 text-center">
                  <button
                    onClick={() => onDelete(h.ticker)}
                    className="text-red-500 hover:text-red-700 text-xs font-medium px-2 py-1 rounded hover:bg-red-50 transition-colors"
                  >
                    Delete
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
