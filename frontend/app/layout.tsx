import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ET Investor Copilot",
  description: "Portfolio-aware signal intelligence for Indian retail investors",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="bg-amber-50 border-b border-amber-200 px-4 py-2 text-sm text-amber-800 text-center">
          ⚠️ ET Investor Copilot is for informational purposes only and is not licensed financial advice.
        </div>
        <main className="min-h-screen bg-gray-50">{children}</main>
      </body>
    </html>
  );
}
