-- Portfolio holdings
CREATE TABLE holdings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL DEFAULT 'demo_user',
    ticker TEXT NOT NULL,
    quantity NUMERIC NOT NULL,
    avg_buy_price NUMERIC NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),   -- used for holding duration (Requirement 15)
    UNIQUE(user_id, ticker)
);

-- Generated alerts
CREATE TABLE alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker TEXT NOT NULL,
    signal_type TEXT NOT NULL,
    summary TEXT NOT NULL,
    recommended_action TEXT,
    confidence TEXT,
    estimated_impact_inr_low NUMERIC,
    estimated_impact_inr_high NUMERIC,
    evidence_chain JSONB,
    bull_case TEXT,
    bear_case TEXT,
    what_to_watch JSONB,
    disclaimer TEXT NOT NULL,
    -- Personalization fields (Requirement 15)
    personalized_opening TEXT,
    holding_duration_days INTEGER,
    unrealised_pnl_inr NUMERIC,
    impact_pct_of_portfolio NUMERIC,
    -- Unreported signal flag (Requirement 16)
    unreported_signal BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Audit trail steps
CREATE TABLE audit_trail (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_id UUID REFERENCES alerts(id),
    agent_name TEXT NOT NULL,
    action TEXT NOT NULL,
    source_urls JSONB,
    model_used TEXT,
    fallback_occurred BOOLEAN DEFAULT FALSE,
    fallback_reason TEXT,
    output_summary TEXT,
    -- Model routing fields (Requirement 13)
    task_type TEXT,
    estimated_cost_saved NUMERIC,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);
