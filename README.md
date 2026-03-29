# ET Investor Copilot

Portfolio-aware signal intelligence agent for Indian retail investors.
**ET AI Hackathon 2026 — Track 6: AI for the Indian Investor**

> Not licensed financial advice. All alerts are for informational purposes only.

---

## What It Does

ET Investor Copilot runs a multi-agent LangGraph pipeline that:

1. Fetches real-time NSE/BSE price data, bulk deal filings, and news
2. Detects signals: breakouts, promoter sell bulk deals, macro events
3. Surfaces **unreported signals** — filings with no news coverage yet
4. Enriches signals with portfolio context, EPS history, and real backtests
5. Generates source-cited, personalized alerts with INR impact estimates
6. Logs every agent step to a full audit trail visible in the UI

---

## Demo Scenarios

Three pre-populated scenarios run without external API calls:

| Scenario | Ticker | Signal |
|---|---|---|
| `bulk_deal` | HDFCBANK.NS | Promoter sells 4.2% equity at 6% discount — unreported signal |
| `breakout` | INFY.NS | 52W high breakout + RSI 78.3 + FII reduction — conflicted signal |
| `macro` | HDFCBANK + INFY | RBI rate cut + SEBI regulation — dual macro, ranked by INR impact |

---

## Setup

### Prerequisites
- Python 3.11+
- Node.js 18+
- API keys: Gemini, OpenAI, Tavily, Supabase

### Backend

```bash
cd backend
pip install -e .
```

Create `backend/.env` (copy from `backend/.env.example`):
```
GEMINI_API_KEY=your_key
OPENAI_API_KEY=your_key
GROQ_API_KEY=your_key          # free at console.groq.com
TAVILY_API_KEY=your_key
SUPABASE_URL=your_url
SUPABASE_ANON_KEY=your_key
```

```bash
uvicorn backend.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
```

Create `frontend/.env.local`:
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

```bash
npm run dev
```

### Supabase Schema

Run `backend/db/schema.sql` in your Supabase SQL editor to create the `holdings`, `alerts`, and `audit_trail` tables.

---

## Architecture

See [`docs/architecture.md`](docs/architecture.md) for the full agent diagram, communication model, tool integrations, and error-handling logic.

**Agent pipeline:**
```
DataFetcher → SignalDetector → ContextEnricher ──────────────┐
                                    └── ExtendedEnricher ────▶ AlertGenerator → AuditLog
                                        (conflicted path)
```

**Key design decisions:**
- LangGraph `StateGraph` with typed shared state — no direct agent-to-agent calls
- `safe_agent_node` wrapper on every node — pipeline never crashes on partial failure
- ModelRouter: **3-tier cascade** — Groq/Llama-3.1-8B (classification, ~$0.000005/call) → Gemini Flash (standard alerts, ~$0.0005/call) → GPT-4o (conflicted signals only, ~$0.02/call). ~72% cost reduction vs all-GPT-4o.
- FilingScanner: detects NSE filings with no news coverage → `unreported_signal` badge

---

## Impact Model

See [`docs/impact_model.md`](docs/impact_model.md) for quantified estimates.

**TL;DR:**
- ~120–150 hours/year saved per investor (58 min per signal event)
- ₹7,500–₹30,000/year in downside avoided via early filing detection
- ~72% LLM cost reduction via model routing (~$21K/year at 1K runs/day)

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14, TypeScript, Tailwind CSS |
| Backend | Python 3.11, FastAPI, LangGraph |
| Agents | LangChain (Google GenAI + OpenAI) |
| Data | yfinance, Tavily Search API |
| Storage | Supabase (PostgreSQL) |
| Deployment | Vercel (frontend), Railway (backend) |

---

## Project Structure

```
backend/
  agents/          # DataFetcher, SignalDetector, ContextEnricher, AlertGenerator
  demo/            # Pre-populated scenario fixtures
  routers/         # FastAPI route handlers
  orchestrator.py  # LangGraph StateGraph definition
  models.py        # All dataclasses and TypedDicts
  main.py          # FastAPI app entry point
frontend/
  app/             # Next.js app router
  components/      # Portfolio, AlertCard, AuditTrail, DemoScenarios
docs/
  architecture.md  # Agent diagram + design decisions
  impact_model.md  # Quantified business impact
```
