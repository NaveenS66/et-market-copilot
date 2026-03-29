# ET Investor Copilot — Architecture Document

## Overview

ET Investor Copilot is a portfolio-aware signal intelligence system for Indian retail investors. It runs a multi-agent LangGraph pipeline that fetches market data, detects signals, enriches them with portfolio context, and generates source-cited, actionable alerts with a full audit trail.

Built solo in ~20 hours for ET AI Hackathon 2026 (Track 6: AI for the Indian Investor).

---

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Frontend (Next.js · Vercel)                     │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │  Portfolio   │  │  Alert Feed  │  │  Audit Trail Panel       │  │
│  │  Manager     │  │  (sorted by  │  │  (expandable per alert)  │  │
│  │  (CRUD)      │  │  INR impact) │  │                          │  │
│  └──────┬───────┘  └──────┬───────┘  └────────────┬─────────────┘  │
└─────────┼─────────────────┼───────────────────────┼────────────────┘
          │  REST            │  REST                 │  REST
          ▼                  ▼                       ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Backend (FastAPI · Railway)                       │
│                                                                     │
│  POST /api/analysis/run          GET /api/alerts                    │
│  POST /api/demo/{scenario}       GET /api/alerts/{id}/audit         │
│  POST /api/portfolio/holding     DELETE /api/portfolio/holding/{t}  │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │              LangGraph Orchestrator (StateGraph)             │   │
│  │                                                              │   │
│  │  ┌────────────┐   ┌────────────┐   ┌──────────────────────┐ │   │
│  │  │ DataFetcher│──▶│SignalDetect│──▶│  ContextEnricher     │ │   │
│  │  │            │   │            │   │  (standard path)     │ │   │
│  │  │ · yfinance │   │ · Breakout │   └──────────┬───────────┘ │   │
│  │  │ · NSE bulk │   │ · Promoter │              │             │   │
│  │  │   deals    │   │   sell     │   ┌──────────▼───────────┐ │   │
│  │  │ · Tavily   │   │ · Conflict │   │  ExtendedEnricher    │ │   │
│  │  │   news     │   │   detect   │   │  (conflicted path)   │ │   │
│  │  │ · Filing   │   │ · Macro    │   │  + BacktestEngine    │ │   │
│  │  │   Scanner  │   │   events   │   └──────────┬───────────┘ │   │
│  │  └────────────┘   └────────────┘              │             │   │
│  │                                               ▼             │   │
│  │                                   ┌───────────────────────┐ │   │
│  │                                   │   AlertGenerator      │ │   │
│  │                                   │   · ModelRouter       │ │   │
│  │                                   │   · Gemini primary    │ │   │
│  │                                   │   · GPT-4o fallback   │ │   │
│  │                                   │   · Personalization   │ │   │
│  │                                   └──────────┬────────────┘ │   │
│  │                                              │              │   │
│  │                                   ┌──────────▼────────────┐ │   │
│  │                                   │   AuditLog Node       │ │   │
│  │                                   │   · Persist to        │ │   │
│  │                                   │     Supabase          │ │   │
│  │                                   │   · Cost summary      │ │   │
│  │                                   └───────────────────────┘ │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
          │                  │                       │
          ▼                  ▼                       ▼
┌──────────────┐   ┌──────────────────┐   ┌──────────────────────────┐
│  yfinance /  │   │  Tavily Search   │   │  Supabase (PostgreSQL)   │
│  NSE Data    │   │  API             │   │                          │
│              │   │                  │   │  · holdings              │
│  · OHLCV     │   │  · News search   │   │  · alerts                │
│  · RSI(14)   │   │  · Filing scan   │   │  · audit_trail           │
│  · 52W H/L   │   │  · Mgmt. notes   │   │                          │
└──────────────┘   └──────────────────┘   └──────────────────────────┘
          │
          ▼
┌──────────────────────────────────┐
│  LLM APIs                        │
│                                  │
│  · Gemini 1.5 Flash (classify)   │
│  · Gemini 1.5 Pro (std alerts)   │
│  · GPT-4o (conflicted alerts /   │
│            fallback)             │
└──────────────────────────────────┘
```

---

## Agent Roles

### 1. DataFetcher Agent
Fetches all raw inputs needed by the pipeline. No LLM calls — pure data retrieval.

| Sub-task | Tool | Fallback |
|---|---|---|
| Price, volume, RSI(14), 52W H/L | yfinance | Gemini grounding search |
| NSE bulk deal disclosures | Tavily (`site:nseindia.com`) | Return empty list, log error |
| News & filings | Tavily (top 5 results) | Return empty list, log error |
| Unreported signal detection | FilingScanner (Tavily cross-ref) | Log error, continue |

The FilingScanner sub-component searches NSE filings directly, then cross-references against news published in the last 24 hours. If a filing exists with no news coverage, the signal is flagged as `unreported_signal=True` and gets a priority boost.

### 2. SignalDetector Agent
Pure deterministic logic — no LLM calls. Classifies signals from raw data.

| Signal Type | Trigger Condition |
|---|---|
| `breakout` | `close >= week52_high` AND `volume > avg_vol_20d × 1.2` |
| `bulk_deal_promoter_sell` | `is_promoter=True` AND `pct_equity > 1.0%` |
| `macro_event` | Macro keywords (RBI, SEBI, rate, repo…) found in news |
| Conflict flag | `overbought` (RSI > 70) + `fii_reduction` → `is_conflicted=True` |

Conflict detection: when ≥ 2 bearish flags attach to a single signal, the signal is marked conflicted and routed to the extended enrichment path.

### 3. ContextEnricher Agent (standard path)
Enriches signals with portfolio context and impact estimates.

- Checks portfolio match for the affected ticker
- For `bulk_deal_promoter_sell`: fetches last 4 quarters EPS trend (yfinance) + management commentary (Tavily)
- Estimates INR impact range using sector sensitivity coefficients × holding value
- For macro events: ranks simultaneous events by absolute INR impact

### 4. ExtendedEnricher Agent (conflicted path)
Runs all standard enrichment, then additionally:

- Calls **BacktestEngine** to compute real historical breakout success rate from 2 years of yfinance data
- Returns `success_rate_pct`, `sample_size`, `avg_gain_pct`, `avg_loss_pct`
- Feeds these into the conflicted alert prompt so the LLM reasons about historical reliability

### 5. AlertGenerator Agent
LLM-powered. Uses **ModelRouter** to select the right model per task.

**ModelRouter routing table:**

| Task | Model | Est. cost/call | Saved vs GPT-4o |
|---|---|---|---|
| Sector tagging | Gemini Flash | ~$0.0001 | ~$0.0199 |
| Promoter detection | Gemini Flash | ~$0.0002 | ~$0.0198 |
| Standard alert | Gemini Pro | ~$0.002 | ~$0.018 |
| Conflicted alert | GPT-4o | ~$0.02 | $0 (baseline) |

Primary model: Gemini. Fallback: GPT-4o (triggered on empty/error response). All routing decisions are logged to the audit trail with cost savings.

Personalization (Requirement 15): for portfolio holdings, the alert opens with a line referencing holding duration, avg buy price, and current position value.

### 6. AuditLog Node
Writes the final alert and full audit trail to Supabase. Computes cumulative cost efficiency summary across all ModelRouter decisions.

---

## Agent Communication

All agents communicate through a shared **LangGraph `PipelineState`** TypedDict — a single immutable state object passed between nodes. Each node returns a new state dict (spread + updates). No direct agent-to-agent calls.

```
PipelineState = {
  ticker, portfolio, scenario_hint,       # inputs
  price_data, bulk_deals, news_results,   # DataFetcher outputs
  filing_scan_result,                     # FilingScanner output
  signals, conflict_report,               # SignalDetector outputs
  enriched_context, portfolio_match,      # ContextEnricher outputs
  alert,                                  # AlertGenerator output
  audit_trail, errors                     # cross-cutting
}
```

The orchestrator uses a **conditional edge** after SignalDetector:
- `is_conflicted=True` → `extended_enrich` → `alert_generate`
- `is_conflicted=False` → `context_enrich` → `alert_generate`

---

## Tool Integrations

| Tool | Purpose | Auth |
|---|---|---|
| yfinance | Price, volume, RSI, EPS history, backtest data | None (public) |
| Tavily Search API | News, NSE filing search, management commentary | API key |
| Google Gemini API | Classification, standard alert generation, fallback data | API key |
| OpenAI GPT-4o | Conflicted alert generation, Gemini fallback | API key |
| Supabase | Portfolio persistence, alert storage, audit trail | URL + anon key |

---

## Error Handling

Every agent node is wrapped in `safe_agent_node()` — a try/except decorator that:
1. Catches any unhandled exception from the node function
2. Appends an error entry to `state["errors"]`
3. Appends an `AuditStep` with `action="error"` and the exception message
4. Returns the partial state so the pipeline continues to the next node

This means a DataFetcher failure (e.g., yfinance timeout) does not crash the pipeline — SignalDetector simply receives `price_data=None` and skips breakout detection. The alert is still generated from whatever data is available.

Additional fallback layers:
- yfinance failure → Gemini grounding search for approximate price data
- Gemini LLM failure → GPT-4o fallback for alert generation
- Tavily zero results → empty list returned, logged, pipeline continues
- Supabase write failure → logged to audit trail, alert still returned to frontend

---

## Data Flow Summary

```
User clicks "Run Analysis"
        │
        ▼
POST /api/analysis/run  (or /api/demo/{scenario})
        │
        ▼
LangGraph pipeline invoked with initial PipelineState
        │
  ┌─────▼──────┐
  │ DataFetcher│  → price, bulk deals, news, filing scan
  └─────┬──────┘
        │
  ┌─────▼──────┐
  │SignalDetect│  → signals[], conflict_report
  └─────┬──────┘
        │
   conflicted?
   ┌────┴────┐
  Yes       No
   │         │
   ▼         ▼
Extended  Standard
Enrich    Enrich    → enriched_context (impact, EPS, backtest)
   │         │
   └────┬────┘
        │
  ┌─────▼──────┐
  │AlertGenerat│  → alert (JSON with evidence_chain, personalization)
  └─────┬──────┘
        │
  ┌─────▼──────┐
  │ AuditLog   │  → persist to Supabase, cost summary
  └─────┬──────┘
        │
        ▼
  Return alert + audit_trail to frontend
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14, TypeScript, Tailwind CSS, Vercel |
| Backend | Python 3.11, FastAPI, LangGraph, Railway |
| Agents | LangChain (Google GenAI + OpenAI adapters) |
| Data | yfinance, Tavily Python SDK |
| Storage | Supabase (PostgreSQL) |
| Testing | pytest, Hypothesis (property-based testing) |
