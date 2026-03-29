# ET Investor Copilot
## ET AI Hackathon 2026 — Track 6: AI for the Indian Investor
### Submission Document

> Not licensed financial advice. All alerts are for informational purposes only.

---

## 1. Problem Statement

18 crore+ retail investors are registered on NSE as of 2025. Every one of them operates at a structural information disadvantage:

- Promoter bulk deal filings appear on NSE within **minutes** of execution — but mainstream financial news covers them **4–24 hours later**
- Conflicting signals (breakout + RSI overbought + FII selling) are never explained together — investors get fragmented, contradictory headlines
- Portfolio-specific impact ("how much does this affect *my* ₹2L holding?") requires manual calculation most retail investors never do
- Monitoring 10+ stocks across NSE filings, news, and technicals manually takes 1–2 hours per day

**ET Investor Copilot closes this gap** — a portfolio-aware signal intelligence agent that detects signals, enriches them with portfolio context, and delivers a source-cited, actionable alert in under 30 seconds.

---

## 2. Architecture Document

### 2.1 System Overview

ET Investor Copilot runs a **multi-agent LangGraph pipeline** with a typed shared state (`PipelineState`). No direct agent-to-agent calls — all communication flows through a single immutable state object passed between nodes.

### 2.2 Agent Pipeline Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                  Frontend (Next.js · Vercel)                 │
│  Portfolio Manager │ Alert Feed (INR ranked) │ Audit Trail   │
└──────────────────────────┬──────────────────────────────────┘
                           │ REST API
┌──────────────────────────▼──────────────────────────────────┐
│                  Backend (FastAPI · Render)                   │
│                                                              │
│  ┌────────────┐   ┌─────────────┐   ┌────────────────────┐  │
│  │ DataFetcher│──▶│SignalDetect │──▶│  ContextEnricher   │  │
│  │            │   │             │   │  (standard path)   │  │
│  │ · yfinance │   │ · Breakout  │   └──────────┬─────────┘  │
│  │ · NSE bulk │   │ · Promoter  │              │            │
│  │   deals    │   │   sell      │   ┌──────────▼─────────┐  │
│  │ · Tavily   │   │ · Conflict  │   │  ExtendedEnricher  │  │
│  │   news     │   │   detect    │   │  (conflicted path) │  │
│  │ · Filing   │   │ · Macro     │   │  + BacktestEngine  │  │
│  │   Scanner  │   │   events    │   └──────────┬─────────┘  │
│  └────────────┘   └─────────────┘              │            │
│                                                ▼            │
│                                   ┌────────────────────┐    │
│                                   │  AlertGenerator    │    │
│                                   │  · ModelRouter     │    │
│                                   │  · Gemini primary  │    │
│                                   │  · GPT-4o fallback │    │
│                                   └──────────┬─────────┘    │
│                                              │              │
│                                   ┌──────────▼─────────┐    │
│                                   │  AuditLog Node     │    │
│                                   │  · Supabase write  │    │
│                                   │  · Cost summary    │    │
│                                   └────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### 2.3 Agent Roles

**DataFetcher** — Pure data retrieval, no LLM calls.
- Price, volume, RSI(14), 52W H/L via yfinance
- NSE bulk deal filings via Tavily (`site:nseindia.com`)
- News via Tavily (top 5 results)
- FilingScanner: cross-references NSE filings against last 24h news → flags `unreported_signal=True` if filing exists with zero news coverage

**SignalDetector** — Pure deterministic logic, no LLM calls.

| Signal | Trigger |
|---|---|
| `breakout` | close ≥ 52W high AND volume > avg_vol_20d × 1.2 |
| `bulk_deal_promoter_sell` | is_promoter=True AND pct_equity > 1.0% |
| `macro_event` | RBI/SEBI/rate/repo keywords in news |
| Conflict flag | RSI > 70 (overbought) + FII reduction → `is_conflicted=True` |

**ContextEnricher (standard path)**
- Portfolio match check for affected ticker
- EPS trend (last 4 quarters via yfinance)
- Management commentary via Tavily
- INR impact range = sector sensitivity coefficient × holding value

**ExtendedEnricher (conflicted path)**
- All standard enrichment, plus:
- BacktestEngine: 2 years of yfinance data → real breakout success rate, avg gain/loss, sample size
- Feeds historical reliability into the conflicted alert prompt

**AlertGenerator** — LLM-powered via ModelRouter.

| Task | Model | Est. cost/call |
|---|---|---|
| Sector tagging | Groq/Llama-3.1-8B | ~$0.000005 |
| Promoter detection | Groq/Llama-3.1-8B | ~$0.00001 |
| Standard alert | Gemini 1.5 Flash | ~$0.0005 |
| Conflicted alert | GPT-4o | ~$0.02 |

**AuditLog Node** — Writes alert + full audit trail to Supabase. Computes cumulative cost savings.

### 2.4 Agent Communication

All agents share a single `PipelineState` TypedDict. Each node returns `{**state, ...updates}`. The orchestrator uses a **conditional edge** after SignalDetector:
- `is_conflicted=True` → ExtendedEnricher → AlertGenerator
- `is_conflicted=False` → ContextEnricher → AlertGenerator

### 2.5 Tool Integrations

| Tool | Purpose | Auth |
|---|---|---|
| yfinance | Price, RSI, EPS, backtest data | None (public) |
| Tavily Search API | News, NSE filing search, management commentary | API key |
| Google Gemini API | Standard alert generation, classification | API key |
| OpenAI GPT-4o | Conflicted alert generation, fallback | API key |
| Groq/Llama-3.1-8B | Classification tasks (cheapest tier) | API key |
| Supabase | Portfolio, alerts, audit trail storage | URL + anon key |

### 2.6 Error Handling

Every agent node is wrapped in `safe_agent_node()` — a try/except decorator that:
1. Catches any unhandled exception
2. Appends error to `state["errors"]`
3. Appends an `AuditStep` with `action="error"`
4. Returns partial state so pipeline continues

Fallback chain:
- yfinance failure → Gemini grounding search for approximate price data
- Gemini failure → GPT-4o fallback for alert generation
- Tavily zero results → empty list, logged, pipeline continues
- Supabase write failure → logged, alert still returned to frontend

---

## 3. Impact Model

### 3.1 Time Saved per Investor

Manual research time per signal event:

| Task | Manual time |
|---|---|
| Check NSE bulk deal filings | 10 min |
| Cross-reference with news | 10 min |
| Look up RSI + volume data | 5 min |
| Read earnings history / mgmt commentary | 15 min |
| Compute portfolio impact in INR | 10 min |
| Synthesise into a decision | 10 min |
| **Total per signal** | **~60 min** |

With ET Investor Copilot: full pipeline < 30 seconds. Time per signal: ~2 min (read + decide).

**Time saved per signal: ~58 minutes**
**Annual time saved per investor: ~120–150 hours** (assuming 2–3 signal events/week)

### 3.2 Downside Avoided via Early Filing Detection

The most differentiated feature is **unreported signal detection** — surfacing NSE bulk deal filings before news coverage.

- Filing-to-news lag on NSE: typically 4–24 hours
- Promoter bulk deal sell events historically precede 5–15% price corrections within 30 days
- Investor holding ₹1.5L in a stock where promoter sells 4.2% equity at 6% discount:
  - Potential downside avoided: 5–10% of ₹1.5L = **₹7,500–₹15,000 per event**

**Annual downside avoided per investor: ₹7,500–₹30,000** (1–2 such events/year, conservative)

### 3.3 LLM Cost Reduction via Model Routing

| Task | Without routing (all GPT-4o) | With routing | Saved |
|---|---|---|---|
| Sector tagging | $0.02 | $0.000005 | $0.019995 |
| Promoter detection | $0.02 | $0.00001 | $0.01999 |
| Standard alert | $0.02 | $0.0005 | $0.0195 |
| Conflicted alert | $0.02 | $0.02 | $0 |
| **Per pipeline run** | **~$0.08** | **~$0.021** | **~$0.059** |

**Cost reduction: ~74% per pipeline run**

At 1,000 runs/day:
- Without routing: $80/day = **$29,200/year**
- With routing: $21/day = **$7,665/year**
- **Annual savings: ~$21,500**

### 3.4 Market Opportunity

| Metric | Value |
|---|---|
| NSE registered retail investors (2025) | 18 crore+ |
| Target segment (tech-savvy, ₹2L+ portfolio) | ~50 lakh |
| Willingness to pay | ₹199–₹499/month |
| TAM at ₹299/month × 50L users | ₹1,495 crore/year (~$180M) |
| Realistic 1% penetration (5L users) | **~$1.8M ARR** |

### 3.5 Summary

| Impact Dimension | Estimate | Key Assumption |
|---|---|---|
| Time saved/investor/year | 120–150 hours | 2–3 signal events/week, 58 min saved each |
| Downside avoided/investor/year | ₹7,500–₹30,000 | 1–2 promoter sell events, 5–10% correction |
| LLM cost reduction | ~74% per run | ModelRouter vs all-GPT-4o baseline |
| Annual infra savings at 1K runs/day | ~$21,500 | $0.059 saved × 365K runs |
| Realistic ARR at 1% TAM | ~$1.8M | ₹299/month × 5L users |

**Core value proposition:** Asymmetric information access — giving retail investors the same filing-first signal detection that institutional desks have had for years, delivered in plain language with portfolio-specific INR impact quantification.

---

## 4. Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14, TypeScript, Tailwind CSS, Vercel |
| Backend | Python 3.11, FastAPI, LangGraph, Render |
| Agents | LangChain (Google GenAI + OpenAI + Groq adapters) |
| Data | yfinance, Tavily Python SDK |
| Storage | Supabase (PostgreSQL) |

---

*Built solo in ~20 hours for ET AI Hackathon 2026 — Track 6: AI for the Indian Investor*
