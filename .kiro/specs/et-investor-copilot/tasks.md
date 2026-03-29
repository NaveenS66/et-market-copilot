# Implementation Plan: ET Investor Copilot

## Overview

Tasks are ordered for the fastest path to a live, judge-ready demo. The strategy is:
1. Get the backend pipeline working end-to-end with mocked data first
2. Wire in real APIs (yfinance, Tavily, Gemini)
3. Build the frontend dashboard
4. Polish the three judging scenarios

The design document, requirements, and all agent prompts are available as context during implementation.

---

## Tasks

- [x] 1. Project scaffolding and environment setup
  - Create monorepo structure: `/backend` (FastAPI) and `/frontend` (Next.js)
  - Set up `/backend/pyproject.toml` with dependencies: `fastapi`, `uvicorn`, `langgraph`, `langchain-google-genai`, `langchain-openai`, `yfinance`, `pandas-ta`, `tavily-python`, `supabase`, `hypothesis`, `pytest`, `python-dotenv`
  - Set up `/frontend` with `npx create-next-app` using TypeScript + Tailwind + shadcn/ui
  - Create `.env.example` files for both backend and frontend with all required keys: `GEMINI_API_KEY`, `OPENAI_API_KEY`, `TAVILY_API_KEY`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`
  - Create Supabase tables by running the SQL schema from the design document (holdings, alerts, audit_trail)
  - _Requirements: 1.3, 6.5, 7.4_

- [x] 2. Core data models and shared types
  - [x] 2.1 Implement Python dataclasses in `/backend/models.py`
    - Implement all dataclasses from the design: `Holding`, `PriceData`, `BulkDeal`, `Signal`, `Flag`, `ConflictReport`, `EnrichedContext`, `AuditStep`, `PipelineState`
    - Implement `AlertResponse` and `EvidenceItem` TypedDicts matching the design schema
    - _Requirements: 2.1, 3.1, 4.1, 5.1_

  - [ ]* 2.2 Write property test for AlertResponse disclaimer invariant
    - **Property 24: Disclaimer invariant**
    - **Validates: Requirements 5.5**
    - Generate random AlertResponse objects and verify disclaimer is always non-empty and contains "not licensed financial advice"

- [x] 3. DataFetcher Agent
  - [x] 3.1 Implement `fetch_price_data(ticker)` in `/backend/agents/data_fetcher.py`
    - Use `yfinance` to fetch OHLCV data for the ticker
    - Compute RSI(14) using `pandas-ta`
    - Compute `avg_volume_20d` from 20-day rolling average
    - Return a `PriceData` dataclass with `source_url` set to `f"https://finance.yahoo.com/quote/{ticker}"`
    - _Requirements: 2.1_

  - [x] 3.2 Implement `fetch_nse_bulk_deals(ticker)` in `/backend/agents/data_fetcher.py`
    - Use Tavily to search `site:nseindia.com bulk deal {ticker}` and parse results into `BulkDeal` objects
    - Set `is_promoter=True` if client_name contains "promoter" or "promoter group" (case-insensitive)
    - Set `filing_url` from the Tavily result URL
    - _Requirements: 2.2_

  - [x] 3.3 Implement `fetch_news(ticker)` using Tavily in `/backend/agents/data_fetcher.py`
    - Search for `{ticker} NSE filing earnings announcement` and return top 5 results
    - Each result must include `source_url` and `retrieved_at` timestamp
    - _Requirements: 2.3_

  - [x] 3.4 Implement Gemini grounding fallback in `/backend/agents/data_fetcher.py`
    - Wrap `fetch_price_data` in try/except; on failure call `gemini_grounding_fallback(ticker)`
    - `gemini_grounding_fallback` uses `langchain-google-genai` with grounding enabled to retrieve price data
    - Append `AuditStep` with `fallback_occurred=True` and `fallback_reason=str(e)`
    - _Requirements: 2.4_

  - [x] 3.5 Implement `data_fetcher_node(state)` — the LangGraph node wrapper
    - Calls fetch_price_data, fetch_nse_bulk_deals, fetch_news in sequence
    - Appends AuditSteps for each call with source URLs and timestamps
    - Wraps entire function in `safe_agent_node` error handler from design
    - _Requirements: 2.7, 6.3_

  - [ ]* 3.6 Write property tests for DataFetcher
    - **Property 5: PriceData completeness** — mock yfinance, verify all fields non-null and in range
    - **Property 6: BulkDeal object completeness** — mock Tavily, verify all BulkDeal fields non-null
    - **Property 7: News results bounded and sourced** — verify len ≤ 5 and all have source_url
    - **Property 8: yfinance fallback on failure** — inject exception, verify fallback_occurred=True in audit
    - **Property 9: Audit trail records source URLs** — verify audit trail has source_url entries
    - **Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.7**

- [x] 4. SignalDetector Agent
  - [x] 4.1 Implement `signal_detector_node(state)` in `/backend/agents/signal_detector.py`
    - Implement breakout detection: `close >= week52_high and volume > avg_volume_20d * 1.2`
    - Implement promoter sell detection: `is_promoter=True and pct_equity > 1.0`
    - Implement overbought flag: attach if `rsi14 > 70` on any breakout signal
    - Implement FII reduction flag: attach if `fii_change_qoq < -1.0` on any breakout signal
    - Implement conflict detection: if signal has ≥ 2 bearish flags, set `is_conflicted=True` and build `ConflictReport`
    - Implement macro event detection: tag portfolio tickers by sector using a hardcoded sector map (NIFTY sector → tickers)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

  - [ ]* 4.2 Write property tests for SignalDetector
    - **Property 10: Breakout signal classification** — for any PriceData meeting criteria, verify breakout signal present
    - **Property 11: Promoter sell signal classification** — for any qualifying BulkDeal, verify signal present
    - **Property 12: Conflicting flag attachment** — verify overbought and FII flags attach correctly
    - **Property 13: Conflict detection threshold** — verify is_conflicted=True when ≥ 2 bearish flags
    - **Property 14: Macro event sector tagging** — verify tagged tickers ⊆ portfolio tickers in sector
    - **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6**

- [x] 5. Checkpoint — pipeline skeleton working
  - Ensure all tests pass, ask the user if questions arise.
  - Manually test DataFetcher + SignalDetector with a real ticker (e.g., RELIANCE.NS) to verify data flows correctly.

- [x] 6. ContextEnricher Agent
  - [x] 6.1 Implement `context_enricher_node(state)` in `/backend/agents/context_enricher.py`
    - Check portfolio match: `portfolio_match = any(h.ticker == ticker for h in state["portfolio"])`
    - For bulk_deal_promoter_sell signals: fetch EPS trend (4 quarters) via yfinance `ticker.quarterly_earnings`, fetch management commentary via Tavily search `{ticker} earnings call transcript site:bseindia.com`
    - For portfolio matches: compute `impact_inr_low` and `impact_inr_high` using `estimate_impact(signal, holding)` — use sector sensitivity coefficients (e.g., rate-sensitive sectors: ±8%, IT: ±3%)
    - _Requirements: 4.1, 4.2, 4.4_

  - [x] 6.2 Implement `extended_enricher_node(state)` in `/backend/agents/context_enricher.py`
    - Call `context_enricher_node` first, then additionally fetch breakout history
    - Implement `fetch_breakout_history(ticker, years=2)`: use yfinance historical data to find all prior breakout events (close ≥ rolling 52W high) and compute percentage that were followed by >5% gain within 30 days
    - Set `enriched_context.breakout_success_rate` to the computed percentage
    - _Requirements: 4.3_

  - [x] 6.3 Implement `estimate_impact(signal, holding)` utility
    - Returns `(impact_low, impact_high)` tuple in INR
    - For bulk deal: use `-15%` to `-5%` of holding value as range
    - For macro rate cut: use sector sensitivity map (banking: +5% to +8%, IT: -1% to +1%, etc.)
    - For macro regulatory: use `-10%` to `-3%` of holding value
    - Ensure `impact_low <= impact_high` always
    - _Requirements: 4.4, 11.2_

  - [x] 6.4 Implement macro event priority ranking
    - When multiple macro events exist in state, sort enriched contexts by `abs(impact_inr_high)` descending and assign `priority_rank` starting from 1
    - _Requirements: 4.5_

  - [ ]* 6.5 Write property tests for ContextEnricher
    - **Property 15: Portfolio match flag accuracy** — verify portfolio_match = (ticker in portfolio)
    - **Property 16: Bulk deal enrichment completeness** — verify eps_trend has 4 items, mgmt_commentary non-empty
    - **Property 17: Breakout success rate range** — verify 0.0 ≤ breakout_success_rate ≤ 100.0
    - **Property 18: Impact estimation for portfolio holdings** — verify impact_low ≤ impact_high, both non-null
    - **Property 19: Impact priority ranking** — verify higher abs impact → lower rank number
    - **Property 32: Impact displayed as range** — verify impact_low < impact_high (strict inequality)
    - **Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5, 11.2**

- [x] 7. AlertGenerator Agent
  - [x] 7.1 Implement prompt builders in `/backend/agents/alert_generator.py`
    - Implement `build_bulk_deal_prompt(state)` using the template from the design document
    - Implement `build_breakout_conflicted_prompt(state)` using the template from the design document
    - Implement `build_macro_event_prompt(state)` — include priority rank, impact range, and reasoning
    - Each prompt must instruct the LLM to return JSON matching `AlertResponse` schema
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [x] 7.2 Implement LLM call with Gemini primary and GPT-4o fallback
    - Implement `gemini_generate(prompt)` using `langchain-google-genai` with `gemini-1.5-flash` model
    - Implement `openai_generate(prompt)` using `langchain-openai` with `gpt-4o` model
    - Implement fallback logic: if Gemini raises or returns response with len < 50, call OpenAI
    - Append AuditStep with `model_used`, `fallback_occurred`, `fallback_reason`
    - _Requirements: 5.6, 5.7_

  - [x] 7.3 Implement `alert_generator_node(state)` — the LangGraph node
    - Select correct prompt builder based on signal type
    - Call LLM with fallback
    - Parse JSON response into `AlertResponse` — use `json.loads` with try/except; on parse failure, build a minimal alert from state data
    - Append `DISCLAIMER_TEXT = "This alert is for informational purposes only and is not licensed financial advice."` to every alert
    - Append AuditStep with full prompt hash and output summary
    - _Requirements: 5.1, 5.5_

  - [ ]* 7.4 Write property tests for AlertGenerator
    - **Property 20: Alert required fields completeness** — mock LLM, verify all required fields non-null
    - **Property 21: Bulk deal alert evidence chain** — verify filing URL present in evidence_chain
    - **Property 22: Conflicted alert structure** — verify bull_case, bear_case non-null; what_to_watch length 2–3; recommended_action not "Buy"/"Sell"
    - **Property 23: Macro event alert impact fields** — verify impact fields non-null for portfolio holdings
    - **Property 24: Disclaimer invariant** — verify disclaimer contains required phrase for all alert types
    - **Property 25: LLM fallback behavior** — inject Gemini failure, verify GPT-4o called and fallback recorded
    - **Property 26: Audit trail model recording** — verify model_used non-null in audit trail
    - **Property 31: RSI evidence numeric precision** — verify RSI evidence_chain item has numeric value + date
    - **Property 34: Non-portfolio alerts omit INR impact** — verify impact fields null when portfolio_match=False
    - **Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 9.3, 11.5**

- [x] 8. LangGraph Orchestrator
  - [x] 8.1 Implement the LangGraph StateGraph in `/backend/orchestrator.py`
    - Define `PipelineState` TypedDict as specified in the design
    - Register all five nodes: `data_fetch`, `signal_detect`, `context_enrich`, `extended_enrich`, `alert_generate`
    - Implement `route_on_conflict(state)` conditional edge function: returns "conflicted" if any signal has `is_conflicted=True`, else "normal"
    - Add `audit_log` node that writes final state to Supabase (alerts table + audit_trail table)
    - Compile the graph with `graph.compile()`
    - _Requirements: 6.1, 6.2, 6.4, 6.5_

  - [x] 8.2 Wrap all agent nodes with `safe_agent_node` error handler
    - Implement `safe_agent_node(node_fn, state)` from the design document
    - Apply wrapper to all five agent nodes
    - _Requirements: 6.3_

  - [ ]* 8.3 Write property tests for Orchestrator
    - **Property 27: Conflicted signal routing** — inject conflicted signal, verify "extended_enrich" in audit trail
    - **Property 28: Error recovery returns partial result** — inject exception in each node, verify errors list non-empty and no exception propagates
    - **Property 29: Pipeline persists to Supabase** — run pipeline with mocked agents, verify Supabase contains alert and audit trail
    - **Validates: Requirements 6.2, 6.3, 6.5**

- [x] 9. FastAPI REST endpoints
  - [x] 9.1 Implement portfolio endpoints in `/backend/routers/portfolio.py`
    - `GET /api/portfolio` — fetch holdings from Supabase, enrich with current price via yfinance, return with unrealised_pnl
    - `POST /api/portfolio/holding` — validate ticker (attempt yfinance fetch; reject if fails), insert into Supabase
    - `DELETE /api/portfolio/holding/{ticker}` — delete from Supabase
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [x] 9.2 Implement analysis endpoints in `/backend/routers/analysis.py`
    - `POST /api/analysis/run` — accept `RunAnalysisRequest`, run orchestrator pipeline for each ticker in portfolio, return list of `AlertResponse`
    - `POST /api/analysis/ticker` — run pipeline for a single ticker (used for demo scenarios)
    - Use `asyncio.gather` to run multiple tickers in parallel
    - _Requirements: 6.1_

  - [x] 9.3 Implement alert and audit endpoints in `/backend/routers/alerts.py`
    - `GET /api/alerts` — fetch alerts from Supabase ordered by `abs(estimated_impact_inr_high)` descending, paginated (limit 20)
    - `GET /api/alerts/{alert_id}/audit` — fetch audit trail entries for alert_id from Supabase
    - _Requirements: 7.4, 11.3_

  - [x] 9.4 Add CORS middleware and health check endpoint to `/backend/main.py`
    - Allow frontend origin (localhost:3000 and Vercel domain)
    - `GET /health` returns `{"status": "ok"}`

- [ ] 10. Checkpoint — full backend pipeline working
  - Ensure all tests pass, ask the user if questions arise.
  - Run the three judging scenarios manually via `POST /api/analysis/ticker` with scenario hints and verify alerts are generated with correct structure.

- [x] 11. Frontend: Portfolio Manager component
  - [x] 11.1 Create `PortfolioTable` component in `/frontend/components/PortfolioTable.tsx`
    - Display holdings in a shadcn/ui `Table` with columns: Ticker, Qty, Avg Buy Price, Current Price, Day Change %, Unrealised P&L
    - Colour-code P&L: green for positive, red for negative
    - _Requirements: 1.5, 8.1_

  - [x] 11.2 Create `AddHoldingForm` component in `/frontend/components/AddHoldingForm.tsx`
    - shadcn/ui `Dialog` with inputs for ticker, quantity, avg buy price
    - On submit: call `POST /api/portfolio/holding`; show error toast if ticker invalid
    - _Requirements: 1.1, 1.4_

  - [x] 11.3 Create portfolio page at `/frontend/app/page.tsx`
    - Fetch portfolio on load via `GET /api/portfolio`
    - Render `PortfolioTable` + `AddHoldingForm` + delete button per row
    - _Requirements: 8.1_

- [x] 12. Frontend: Alert Feed and Audit Trail
  - [x] 12.1 Create `AlertCard` component in `/frontend/components/AlertCard.tsx`
    - Show signal type badge (colour-coded: red for bulk deal, amber for conflicted, blue for macro), ticker, summary, confidence badge
    - Expandable section showing: recommended action, estimated impact range in INR, bull case / bear case (if conflicted), what to watch list (if conflicted)
    - Evidence Chain section: collapsible list of clickable source links
    - "Show Reasoning" button that opens audit trail panel
    - _Requirements: 8.2, 8.3, 9.5_

  - [x] 12.2 Create `AuditTrailPanel` component in `/frontend/components/AuditTrailPanel.tsx`
    - Fetch audit trail from `GET /api/alerts/{alert_id}/audit` on open
    - Render each AuditStep as a timeline item: agent name, action, timestamp, source URLs, model used, fallback indicator
    - _Requirements: 7.1, 7.2, 7.3, 8.3_

  - [x] 12.3 Create alert feed page section in `/frontend/app/page.tsx`
    - Fetch alerts from `GET /api/alerts` on load and after pipeline run
    - Render list of `AlertCard` components sorted by impact (API handles sort)
    - _Requirements: 8.2, 11.3_

- [-] 13. Frontend: Run Analysis and Progress Indicator
  - [x] 13.1 Create `RunAnalysisButton` component in `/frontend/components/RunAnalysisButton.tsx`
    - Button that calls `POST /api/analysis/run` with current portfolio
    - While running: show shadcn/ui `Progress` bar and current step name (poll `/api/analysis/status` or use SSE)
    - On complete: refresh alert feed
    - _Requirements: 8.4, 8.5_

  - [ ] 13.2 Implement Server-Sent Events (SSE) endpoint in `/backend/routers/analysis.py`
    - `GET /api/analysis/stream/{run_id}` — stream pipeline step names as SSE events
    - Update `PipelineState` to include `current_step: str` field
    - Each agent node updates `current_step` before executing
    - _Requirements: 8.5_

- [x] 14. Frontend: Disclaimer banner and responsive layout
  - Add a persistent top banner in `/frontend/app/layout.tsx`: "⚠️ ET Investor Copilot is for informational purposes only and is not licensed financial advice."
  - Ensure layout uses Tailwind responsive classes (sm/md/lg breakpoints) for mobile usability
  - _Requirements: 8.6, 8.7_

- [x] 15. Three judging scenario demo fixtures
  - [x] 15.1 Create `/backend/demo/scenarios.py` with hardcoded scenario inputs
    - `SCENARIO_BULK_DEAL`: HDFC Bank promoter sell 4.2% at 6% discount — pre-populated PipelineState with realistic data
    - `SCENARIO_BREAKOUT_CONFLICTED`: Infosys 52W high breakout, RSI=78, FII -2.1% QoQ — pre-populated state
    - `SCENARIO_MACRO_DUAL`: RBI rate cut + SEBI regulatory change, portfolio with 8 stocks including HDFC and Infosys
    - _Requirements: 9.1, 9.2, 9.3_

  - [x] 15.2 Add `POST /api/demo/{scenario_name}` endpoint
    - Accepts `"bulk_deal"`, `"breakout"`, or `"macro"` as scenario name
    - Loads the corresponding fixture from `scenarios.py` and runs it through the real AlertGenerator (LLM still called, data is pre-populated)
    - Returns the alert immediately — no external API calls needed for demo reliability
    - _Requirements: 9.4, 12.4_

  - [ ]* 15.3 Write unit tests for all three scenario outputs
    - Test that SCENARIO_BULK_DEAL produces an alert with filing URL, distress assessment, and EPS trend
    - Test that SCENARIO_BREAKOUT_CONFLICTED produces an alert with bull_case, bear_case, what_to_watch, and non-binary recommendation
    - Test that SCENARIO_MACRO_DUAL produces two alerts sorted by impact with impact quantification
    - **Validates: Requirements 9.1, 9.2, 9.3**

- [ ] 16. Checkpoint — full end-to-end demo working
  - Ensure all tests pass, ask the user if questions arise.
  - Run all three demo scenarios via the frontend and verify the UI renders correctly with audit trail visible.

- [x] 19. ModelRouter — cost-efficient LLM routing
  - [x] 19.1 Implement `ModelRouter` class in `/backend/agents/model_router.py`
    - Implement `ROUTING_TABLE` dict mapping task types to (model_name, cost_per_call) as specified in the design
    - Implement `route(task_type)` returning (model_name, cost_saved_vs_gpt4o)
    - Implement `log_routing(task_type, audit_trail)` that appends an AuditStep with agent="ModelRouter", model_used, estimated_cost_saved, and a human-readable note (e.g., "Used gemini-flash for sector_tagging — saved ~$0.0199 vs GPT-4o")
    - _Requirements: 13.1, 13.2, 13.3_

  - [x] 19.2 Wire ModelRouter into DataFetcher and AlertGenerator
    - In `data_fetcher_node`: call `model_router.log_routing("sector_tagging", ...)` and `model_router.log_routing("promoter_detection", ...)` before the relevant classification steps
    - In `alert_generator_node`: call `model_router.log_routing("conflicted_alert", ...)` or `model_router.log_routing("standard_alert", ...)` based on `signal.is_conflicted`
    - Replace hardcoded model names in `gemini_generate` / `openai_generate` calls with the model returned by `model_router.route(task_type)`
    - _Requirements: 13.1, 13.2_

  - [x] 19.3 Add cumulative cost efficiency summary to `audit_log` node
    - In `audit_log_node`, sum all `estimated_cost_saved` values from ModelRouter audit entries
    - Append a final AuditStep with agent="ModelRouter", action="cost_summary", output_summary="Total estimated savings: $X.XXXX vs all-GPT-4o baseline"
    - _Requirements: 13.5_

  - [x] 19.4 Add "Model Routing" section to `AuditTrailPanel` frontend component
    - Filter audit trail entries where agent_name="ModelRouter" and render them as a dedicated "Model Routing" subsection
    - Display each routing decision as: "{model} for {task_type} — saved ~${cost_saved}"
    - Display cumulative savings total at the bottom of the section
    - _Requirements: 13.4_

  - [ ]* 19.5 Write property tests for ModelRouter
    - **Property 35: Classification tasks use Gemini Flash** — for any routing call with task_type in classification set, verify model_used="gemini-flash" in audit trail
    - **Property 36: Conflicted alerts use GPT-4o** — for any conflicted signal pipeline run, verify routing entry has model_used="gpt-4o"
    - **Property 37: Cost savings non-negative** — for any routing decision, verify estimated_cost_saved ≥ 0
    - **Validates: Requirements 13.1, 13.2, 13.3**

- [x] 20. BacktestEngine — real historical breakout success rate
  - [x] 20.1 Implement `compute_breakout_success_rate(ticker, years=2)` in `/backend/agents/backtest_engine.py`
    - Fetch `yf.Ticker(ticker).history(period=f"{years}y")` — real data, no mocking in production
    - Compute `rolling_52w_high` as 252-day rolling max shifted by 1 (no lookahead)
    - Compute `avg_vol_20d` as 20-day rolling mean shifted by 1
    - Identify breakout days: `close >= rolling_52w_high AND volume > avg_vol_20d * 1.2`
    - For each breakout, find the closing price 30 calendar days later; classify as success if gain > 5%
    - Return `BacktestResult` dataclass with success_rate_pct, sample_size, avg_gain_pct, avg_loss_pct
    - If sample_size < 1, return BacktestResult with success_rate_pct=None and note="Insufficient historical data"
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5_

  - [x] 20.2 Wire BacktestEngine into `extended_enricher_node`
    - Replace the existing `fetch_breakout_history` stub with a call to `compute_breakout_success_rate`
    - Store the full `BacktestResult` in `enriched_context.backtest_result`
    - Set `enriched_context.breakout_success_rate = backtest_result.success_rate_pct`
    - Update the conflicted breakout prompt to include `avg_gain_pct` and `avg_loss_pct` alongside `success_rate_pct` and `sample_size`
    - _Requirements: 14.1, 14.5_

  - [ ]* 20.3 Write property tests for BacktestEngine
    - **Property 38: Success rate in valid range** — for any BacktestResult with sample_size ≥ 1, verify success_rate_pct ∈ [0.0, 100.0] and avg_gain/loss non-null
    - **Property 39: Null result on zero sample** — mock yfinance to return data with no breakout events, verify success_rate_pct=None and sample_size=0
    - **Validates: Requirements 14.3, 14.4**

- [x] 21. Portfolio Memory — personalized holding context in alerts
  - [x] 21.1 Update `Holding` dataclass and Supabase fetch to include `created_at`
    - Add `created_at: datetime` field to the `Holding` dataclass (already in DB schema via DEFAULT NOW())
    - Update `GET /api/portfolio` handler to read `created_at` from Supabase and populate `holding.created_at`
    - _Requirements: 15.3_

  - [x] 21.2 Implement personalized context computation in `alert_generator_node`
    - When `portfolio_match=True`, compute `holding_duration_days = (datetime.utcnow() - holding.created_at).days`
    - Compute `unrealised_pnl_inr = (current_price - avg_buy_price) * quantity`
    - Compute `total_portfolio_value = sum(h.quantity * h.current_price for h in portfolio)`
    - Compute `impact_pct_of_portfolio = abs(impact_inr_high) / total_portfolio_value * 100`
    - Build `personalized_opening` string as specified in the design (holding duration, avg price, position value)
    - Set all four fields on the `AlertResponse` object
    - _Requirements: 15.1, 15.2, 15.4_

  - [x] 21.3 Render personalized opening in `AlertCard` frontend component
    - When `alert.personalized_opening` is non-null, render it as a highlighted callout block at the top of the expanded alert view (e.g., blue-tinted background, italic text)
    - Display `impact_pct_of_portfolio` as "Impact: X.X% of total portfolio" beneath the INR impact range
    - _Requirements: 15.1, 15.2_

  - [ ]* 21.4 Write property tests for personalized alert fields
    - **Property 40: Personalized alert fields for portfolio holdings** — for any alert with portfolio_match=True, verify holding_duration_days ≥ 0, unrealised_pnl_inr non-null, impact_pct_of_portfolio ∈ [0.0, 100.0]
    - **Validates: Requirements 15.1**

- [x] 22. FilingScanner — unreported signal detection
  - [x] 22.1 Implement `FilingScanner` in `/backend/agents/filing_scanner.py`
    - Implement `scan_for_unreported_signals(ticker)` as specified in the design
    - Step 1: Tavily search with `site:nseindia.com/companies-listing/corporate-filings/bulk-deals {ticker}` and `days=1`
    - Step 2: Tavily search for news excluding nseindia.com and bseindia.com domains, `days=1`
    - Set `is_unreported = len(filing_results) > 0 and len(news_results) == 0`
    - Return `FilingScanResult` dataclass
    - Append AuditStep recording both the filing URL and news cross-reference result
    - _Requirements: 16.1, 16.2, 16.5_

  - [x] 22.2 Wire FilingScanner into `data_fetcher_node`
    - After `fetch_nse_bulk_deals`, call `scan_for_unreported_signals(ticker)` and store result in state
    - Add `filing_scan_result: FilingScanResult | None` field to `PipelineState`
    - _Requirements: 16.1_

  - [x] 22.3 Wire unreported signal flag into SignalDetector and AlertGenerator
    - In `signal_detector_node`: if `state["filing_scan_result"].is_unreported`, set `signal.is_unreported = True` on any bulk deal signal
    - In `alert_generator_node`: set `alert.unreported_signal = signal.is_unreported`
    - In priority ranking logic: boost unreported signals by 1 rank position
    - _Requirements: 16.3_

  - [x] 22.4 Add "🔍 Unreported Signal" badge to `AlertCard` frontend component
    - When `alert.unreported_signal === true`, render a badge with text "🔍 Unreported Signal" using amber/yellow styling (e.g., `bg-amber-100 text-amber-800`) next to the signal type badge
    - _Requirements: 16.4_

  - [ ]* 22.5 Write property tests for FilingScanner
    - **Property 41: Unreported signal priority boost** — for any two alerts of same type where one is unreported, verify unreported has lower rank number
    - **Property 42: FilingScanner cross-reference completeness** — verify is_unreported=True implies news_count=0, and is_unreported=False with has_filing=True implies news_count ≥ 1
    - **Validates: Requirements 16.2, 16.3**

- [ ] 23. Checkpoint — all four differentiators integrated
  - Ensure all tests pass, ask the user if questions arise.
  - Run the breakout scenario via `POST /api/demo/breakout` and verify: ModelRouter entries visible in audit trail, BacktestEngine returns real sample_size ≥ 0, personalized_opening present in alert, unreported_signal badge renders if applicable.

- [ ] 17. Deployment
  - [ ] 17.1 Deploy backend to Railway
    - Create `Procfile`: `web: uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
    - Set all environment variables in Railway dashboard
    - Verify `/health` endpoint responds

  - [ ] 17.2 Deploy frontend to Vercel
    - Set `NEXT_PUBLIC_API_URL` environment variable to Railway backend URL
    - Verify portfolio page loads and "Run Analysis" triggers the backend

- [ ] 18. Final checkpoint — live demo URL verified
  - Ensure all tests pass, ask the user if questions arise.
  - Verify all three demo scenarios work on the live Vercel URL.
  - Verify audit trail is visible in the UI for each scenario.
  - Verify disclaimer banner is present on all pages.

---

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Demo scenario fixtures (Task 15) are the most important tasks for hackathon reliability — do these before polishing the UI
- The SSE streaming (Task 13.2) can be replaced with a simple polling approach if time is short
- Property tests (Tasks 3.6, 4.2, 6.5, 7.4, 8.3, 19.5, 20.3, 21.4, 22.5) are optional but strongly recommended — they directly validate the judging criteria
- Tasks 19–22 implement the four differentiators; Task 23 is the integration checkpoint for them
- Each task references specific requirements for traceability
