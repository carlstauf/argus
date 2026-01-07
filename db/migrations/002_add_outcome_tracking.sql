-- ARGUS Database Migration v2.0
-- Outcome Tracking & Signal Performance
-- PostgreSQL 14+

-- ============================================================
-- ALERTS TABLE: Add outcome tracking fields
-- ============================================================

-- Track market resolution outcome
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS 
    market_resolution VARCHAR(10);  -- 'YES', 'NO', 'INVALID', NULL (pending)

-- Did following this signal make money?
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS 
    was_profitable BOOLEAN;

-- Hypothetical P&L if you bet $100 on this signal
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS 
    hypothetical_pnl_usd DECIMAL(20,2);

-- When was this alert's outcome determined
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS 
    resolved_at TIMESTAMP;

-- Adjusted confidence (after time-to-resolution weighting)
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS 
    adjusted_confidence DECIMAL(5,4);

-- Hours until market resolution at time of alert
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS 
    hours_to_resolution DECIMAL(10,2);

-- Position sizing recommendation
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS 
    recommended_size_usd DECIMAL(20,2);

-- Kelly fraction for this signal
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS 
    kelly_fraction DECIMAL(10,6);

-- Is this a composite/mega signal?
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS 
    is_composite BOOLEAN DEFAULT FALSE;

-- Component alert types (for composite signals)
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS 
    component_types JSONB;

-- ============================================================
-- TABLE: signal_performance (Algorithm Performance Tracking)
-- ============================================================
CREATE TABLE IF NOT EXISTS signal_performance (
    id BIGSERIAL PRIMARY KEY,
    alert_type VARCHAR(50) NOT NULL UNIQUE,
    
    -- Performance metrics (rolling 30 days)
    total_signals INT DEFAULT 0,
    profitable_signals INT DEFAULT 0,
    win_rate DECIMAL(5,4),
    avg_confidence_score DECIMAL(5,4),
    total_hypothetical_pnl DECIMAL(20,2) DEFAULT 0,
    
    -- Best performing conditions
    best_category VARCHAR(100),
    best_hour_utc INT,
    avg_hours_to_resolution DECIMAL(10,2),
    
    -- Timestamps
    computed_at TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_signal_perf_type ON signal_performance(alert_type);
CREATE INDEX IF NOT EXISTS idx_signal_perf_winrate ON signal_performance(win_rate DESC);

-- ============================================================
-- WALLET_PROFILES: Add signal accuracy tracking
-- ============================================================

-- Historical accuracy of signals from this wallet
ALTER TABLE wallet_profiles ADD COLUMN IF NOT EXISTS 
    signal_accuracy DECIMAL(5,4);

-- Number of signals generated for this wallet
ALTER TABLE wallet_profiles ADD COLUMN IF NOT EXISTS
    signals_generated INT DEFAULT 0;

-- Number of profitable signals
ALTER TABLE wallet_profiles ADD COLUMN IF NOT EXISTS
    signals_profitable INT DEFAULT 0;

-- Follow priority based on performance
ALTER TABLE wallet_profiles ADD COLUMN IF NOT EXISTS
    follow_priority VARCHAR(20) DEFAULT 'NORMAL';  -- 'PRIORITY', 'NORMAL', 'IGNORE'

-- ============================================================
-- INDEXES for performance
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_alerts_resolution ON alerts(market_resolution);
CREATE INDEX IF NOT EXISTS idx_alerts_profitable ON alerts(was_profitable);
CREATE INDEX IF NOT EXISTS idx_alerts_composite ON alerts(is_composite) WHERE is_composite = TRUE;
CREATE INDEX IF NOT EXISTS idx_wallets_follow ON wallet_profiles(follow_priority) WHERE follow_priority = 'PRIORITY';

-- ============================================================
-- End of Migration
-- ============================================================
