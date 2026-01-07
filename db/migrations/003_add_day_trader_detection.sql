-- ARGUS Database Migration v3.0
-- Day Trader Detection & Insider Targeting
-- PostgreSQL 14+

-- ============================================================
-- WALLETS TABLE: Add day trader tracking columns
-- ============================================================

-- Flag for identified day traders (to exclude from alerts)
ALTER TABLE wallets ADD COLUMN IF NOT EXISTS 
    is_day_trader BOOLEAN DEFAULT FALSE;

-- 7-day trading stats (updated periodically)
ALTER TABLE wallets ADD COLUMN IF NOT EXISTS 
    trades_7d INT DEFAULT 0;

ALTER TABLE wallets ADD COLUMN IF NOT EXISTS 
    unique_markets_7d INT DEFAULT 0;

ALTER TABLE wallets ADD COLUMN IF NOT EXISTS 
    avg_trade_size_7d DECIMAL(20,2);

ALTER TABLE wallets ADD COLUMN IF NOT EXISTS 
    trade_size_cv DECIMAL(10,4);  -- Coefficient of variation

-- Lifetime focus metrics
ALTER TABLE wallets ADD COLUMN IF NOT EXISTS 
    unique_markets_ever INT DEFAULT 0;

-- Insider score (0-100, higher = more likely insider)
ALTER TABLE wallets ADD COLUMN IF NOT EXISTS 
    insider_score INT DEFAULT 50;

-- ============================================================
-- INDEX for day trader queries
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_wallets_day_trader 
    ON wallets(is_day_trader) WHERE is_day_trader = TRUE;

CREATE INDEX IF NOT EXISTS idx_wallets_insider_score 
    ON wallets(insider_score DESC);

-- ============================================================
-- End of Migration
-- ============================================================
