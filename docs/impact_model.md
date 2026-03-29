# ET Investor Copilot — Impact Model

## Problem Statement

Indian retail investors (18 crore+ registered on NSE as of 2025) face a structural information disadvantage:

- Promoter bulk deal filings appear on NSE within minutes of execution, but mainstream financial news covers them hours to days later
- Conflicting signals (e.g., breakout + RSI overbought + FII selling) are rarely explained together — investors get fragmented, contradictory headlines
- Portfolio-specific impact (how much does this event affect *my* ₹2L holding?) requires manual calculation most retail investors don't do
- Monitoring 10+ stocks across NSE filings, news, and technicals manually takes 1–2 hours per day

---

## Impact Dimensions

### 1. Time Saved per Investor

**Manual research time per signal event:**

| Task | Manual time |
|---|---|
| Check NSE bulk deal filings | 10 min |
| Cross-reference with news | 10 min |
| Look up RSI + volume data | 5 min |
| Read earnings history / mgmt commentary | 15 min |
| Compute portfolio impact in INR | 10 min |
| Synthesise into a decision | 10 min |
| **Total per signal** | **~60 min** |

**With ET Investor Copilot:**
- Full pipeline runs in < 30 seconds
- Output is a structured, source-cited alert with INR impact pre-calculated
- Time per signal: ~2 minutes (read + decide)

**Time saved per signal event: ~58 minutes**

Assumption: an active retail investor encounters 2–3 material signal events per week across their portfolio.

**Weekly time saved: ~2–3 hours**
**Annual time saved per investor: ~120–150 hours**

---

### 2. Cost of Missed Signals (Revenue Recovered)

The most differentiated feature is **unreported signal detection** — surfacing bulk deal filings before they appear in news.

**Back-of-envelope:**

- Average retail investor portfolio size in India: ₹3–5 lakh (source: SEBI investor survey 2023)
- Promoter bulk deal sell events historically precede 5–15% price corrections within 30 days (based on NSE data patterns)
- If an investor holds ₹1.5L in a stock where a promoter sells 4.2% equity at a 6% discount to market:
  - Potential downside avoided by acting early: 5–10% of ₹1.5L = **₹7,500–₹15,000 per event**
- Filing-to-news lag on NSE: typically 4–24 hours
- The system detects the filing within minutes of it appearing on NSE

**Estimated value of early detection per event: ₹7,500–₹15,000**

Assumption: 1–2 such events per year per active investor portfolio. Conservative estimate.

**Annual downside avoided per investor: ₹7,500–₹30,000**

---

### 3. Cost Efficiency (Model Routing)

The ModelRouter routes tasks to the cheapest model that can handle them:

| Task | Without routing (all GPT-4o) | With routing | Saved |
|---|---|---|---|
| Sector tagging | $0.02 | $0.0001 | $0.0199 |
| Promoter detection | $0.02 | $0.0002 | $0.0198 |
| Standard alert | $0.02 | $0.002 | $0.018 |
| Conflicted alert | $0.02 | $0.02 | $0 |
| **Per pipeline run** | **~$0.08** | **~$0.022** | **~$0.058** |

**Cost reduction per pipeline run: ~72%**

At 1,000 analysis runs/day (modest SaaS scale):
- Without routing: $80/day = **$29,200/year**
- With routing: $22/day = **$8,030/year**
- **Annual infrastructure savings: ~$21,000**

---

### 4. Market Opportunity

| Metric | Value |
|---|---|
| NSE registered retail investors (2025) | 18 crore+ |
| Active traders (monthly) | ~3–4 crore |
| Target segment (tech-savvy, ₹2L+ portfolio) | ~50 lakh |
| Willingness to pay for signal intelligence | ₹199–₹499/month |
| TAM at ₹299/month × 50L users | ₹1,495 crore/year (~$180M) |
| Realistic 1% penetration (5L users) | **₹14.95 crore/year (~$1.8M ARR)** |

---

## Summary

| Impact Dimension | Estimate | Assumptions |
|---|---|---|
| Time saved per investor/year | 120–150 hours | 2–3 signal events/week, 58 min saved each |
| Downside avoided per investor/year | ₹7,500–₹30,000 | 1–2 promoter sell events, 5–10% correction |
| Infrastructure cost reduction | ~72% per run | ModelRouter vs all-GPT-4o baseline |
| Annual infra savings at 1K runs/day | ~$21,000 | $0.058 saved × 365K runs |
| Realistic ARR at 1% TAM penetration | ~$1.8M | ₹299/month × 5L users |

The core value proposition is **asymmetric information access** — giving retail investors the same filing-first signal detection that institutional desks have had for years, delivered in plain language with portfolio-specific impact quantification.
