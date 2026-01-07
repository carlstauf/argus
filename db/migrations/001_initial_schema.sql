-- ARGUS Database Schema v1.0
-- PostgreSQL 14+
-- The PANOPTICON: Wallet Surveillance System

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "btree_gin";

-- ============================================================
-- TABLE: wallets (The Identity Registry)
-- ============================================================
CREATE TABLE wallets (
    address VARCHAR(42) PRIMARY KEY,

    -- Lifecycle
    first_seen_at TIMESTAMP NOT NULL,
    last_active_at TIMESTAMP NOT NULL,

    -- Activity Metrics
    total_trades INT DEFAULT 0,
    total_volume_usd DECIMAL(20,2) DEFAULT 0,
    total_pnl_usd DECIMAL(20,2) DEFAULT 0,

    -- Performance
    win_rate DECIMAL(5,4), -- 0.0000 to 1.0000
    avg_position_size_usd DECIMAL(20,2),
    avg_hold_time_hours DECIMAL(10,2),

    -- Freshness Index (0-100, 100 = brand new)
    freshness_score INT,

    -- Risk Flags
    is_suspected_insider BOOLEAN DEFAULT FALSE,
    is_whale BOOLEAN DEFAULT FALSE,
    is_copy_worthy BOOLEAN DEFAULT FALSE,

    -- Behavioral Metadata
    total_markets_traded INT DEFAULT 0,
    favorite_categories JSONB, -- ['politics', 'crypto', 'sports']

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_wallets_freshness ON wallets(first_seen_at DESC);
CREATE INDEX idx_wallets_last_active ON wallets(last_active_at DESC);
CREATE INDEX idx_wallets_whale ON wallets(is_whale) WHERE is_whale = TRUE;
CREATE INDEX idx_wallets_insider ON wallets(is_suspected_insider) WHERE is_suspected_insider = TRUE;
CREATE INDEX idx_wallets_copy ON wallets(is_copy_worthy) WHERE is_copy_worthy = TRUE;

-- ============================================================
-- TABLE: markets (The Battlegrounds)
-- ============================================================
CREATE TABLE markets (
    condition_id VARCHAR(66) PRIMARY KEY,

    -- Market Details
    question TEXT NOT NULL,
    slug VARCHAR(500),
    category VARCHAR(100),

    -- Timing
    created_at TIMESTAMP DEFAULT NOW(),
    end_date TIMESTAMP,
    resolved_at TIMESTAMP,

    -- Status
    status VARCHAR(20) DEFAULT 'ACTIVE', -- 'ACTIVE', 'CLOSED', 'RESOLVED'
    resolution VARCHAR(10), -- 'YES', 'NO', 'INVALID'

    -- Market Metrics
    total_volume_usd DECIMAL(20,2) DEFAULT 0,
    current_liquidity_usd DECIMAL(20,2) DEFAULT 0,
    unique_traders INT DEFAULT 0,

    -- Current Pricing
    current_yes_price DECIMAL(10,8),
    current_no_price DECIMAL(10,8),

    -- Metadata
    icon_url TEXT,
    event_slug VARCHAR(500),

    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_markets_status ON markets(status);
CREATE INDEX idx_markets_category ON markets(category);
CREATE INDEX idx_markets_end_date ON markets(end_date DESC) WHERE status = 'ACTIVE';
CREATE INDEX idx_markets_volume ON markets(total_volume_usd DESC);

-- ============================================================
-- TABLE: trades (The Transaction Log)
-- ============================================================
CREATE TABLE trades (
    id BIGSERIAL PRIMARY KEY,

    -- Identifiers
    transaction_hash VARCHAR(66) UNIQUE NOT NULL,
    asset_id VARCHAR(100),

    -- Participants
    wallet_address VARCHAR(42) REFERENCES wallets(address),
    proxy_wallet VARCHAR(42), -- Polymarket's proxy wallet

    -- Market
    condition_id VARCHAR(66) REFERENCES markets(condition_id),

    -- Trade Details
    side VARCHAR(10) NOT NULL, -- 'BUY' or 'SELL'
    outcome VARCHAR(10) NOT NULL, -- 'Yes' or 'No'
    outcome_index INT,
    size DECIMAL(20,8) NOT NULL,
    price DECIMAL(20,8) NOT NULL,
    value_usd DECIMAL(20,2) NOT NULL,

    -- Timing
    timestamp BIGINT NOT NULL, -- Unix timestamp
    executed_at TIMESTAMP NOT NULL,

    -- Intelligence Metadata
    wallet_age_at_trade INT, -- Seconds since wallet first seen
    is_anomalous BOOLEAN DEFAULT FALSE, -- Trade size > 2σ

    -- News Correlation
    nearest_news_event_id BIGINT, -- FK to news_events
    news_distance_seconds INT, -- Negative = trade BEFORE news

    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_trades_wallet ON trades(wallet_address, executed_at DESC);
CREATE INDEX idx_trades_market ON trades(condition_id, executed_at DESC);
CREATE INDEX idx_trades_time ON trades(executed_at DESC);
CREATE INDEX idx_trades_anomalous ON trades(is_anomalous) WHERE is_anomalous = TRUE;
CREATE INDEX idx_trades_hash ON trades(transaction_hash);

-- ============================================================
-- TABLE: news_events (The External Context)
-- ============================================================
CREATE TABLE news_events (
    id BIGSERIAL PRIMARY KEY,

    -- Content
    headline TEXT NOT NULL,
    source VARCHAR(100) NOT NULL, -- 'twitter', 'bloomberg', 'reuters', 'polymarket'
    source_url TEXT,
    full_text TEXT,

    -- Timing
    published_at TIMESTAMP NOT NULL,
    detected_at TIMESTAMP DEFAULT NOW(),

    -- Sentiment Analysis
    sentiment_score DECIMAL(5,4), -- -1.0 (negative) to 1.0 (positive)
    confidence_score DECIMAL(5,4), -- 0.0 to 1.0 (how definitive is the news)
    keywords JSONB, -- ['election', 'confirmed', 'official']

    -- Market Correlation
    related_condition_ids JSONB, -- ['0xabc...', '0xdef...']

    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_news_published ON news_events(published_at DESC);
CREATE INDEX idx_news_keywords ON news_events USING GIN(keywords);
CREATE INDEX idx_news_detected ON news_events(detected_at DESC);

-- ============================================================
-- TABLE: wallet_profiles (The Intelligence Layer)
-- ============================================================
CREATE TABLE wallet_profiles (
    wallet_address VARCHAR(42) PRIMARY KEY REFERENCES wallets(address),

    -- Behavioral Patterns
    preferred_trade_hour_utc INT, -- 0-23
    avg_time_before_resolution_hours DECIMAL(10,2),
    trades_before_news_count INT DEFAULT 0,
    trades_after_news_count INT DEFAULT 0,

    -- Performance Metrics
    sharpe_ratio DECIMAL(10,4),
    max_drawdown_pct DECIMAL(5,2),
    roi_pct DECIMAL(10,2),
    win_streak INT DEFAULT 0,

    -- Insider Scoring
    insider_confidence_score DECIMAL(5,4) DEFAULT 0, -- 0.0 to 1.0
    insider_signals JSONB, -- Array of evidence objects

    -- Copy Trade Worthiness
    copy_score INT DEFAULT 0, -- 0-100
    copy_rank INT,

    -- Last Computation
    computed_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_profiles_insider_score ON wallet_profiles(insider_confidence_score DESC);
CREATE INDEX idx_profiles_copy_score ON wallet_profiles(copy_score DESC);
CREATE INDEX idx_profiles_roi ON wallet_profiles(roi_pct DESC);

-- ============================================================
-- TABLE: alerts (The Signal Generator)
-- ============================================================
CREATE TABLE alerts (
    id BIGSERIAL PRIMARY KEY,

    -- Classification
    alert_type VARCHAR(50) NOT NULL,
    -- 'INSIDER_ALERT', 'WHALE_MOVE', 'FRESH_WALLET', 'SPOOF_DETECTED', 'REALITY_GAP'
    severity VARCHAR(20) NOT NULL, -- 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'

    -- Context
    wallet_address VARCHAR(42) REFERENCES wallets(address),
    condition_id VARCHAR(66) REFERENCES markets(condition_id),
    trade_id BIGINT REFERENCES trades(id),

    -- Message
    title TEXT NOT NULL,
    description TEXT,

    -- Confidence
    confidence_score DECIMAL(5,4), -- How confident is this alert (0.0 to 1.0)

    -- Evidence (JSONB for flexibility)
    supporting_data JSONB,

    -- User Interaction
    is_read BOOLEAN DEFAULT FALSE,
    is_dismissed BOOLEAN DEFAULT FALSE,
    is_actionable BOOLEAN DEFAULT TRUE,

    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_alerts_type ON alerts(alert_type);
CREATE INDEX idx_alerts_severity ON alerts(severity);
CREATE INDEX idx_alerts_unread ON alerts(is_read) WHERE is_read = FALSE;
CREATE INDEX idx_alerts_time ON alerts(created_at DESC);
CREATE INDEX idx_alerts_wallet ON alerts(wallet_address);
CREATE INDEX idx_alerts_market ON alerts(condition_id);

-- ============================================================
-- TABLE: order_book_snapshots (For SEISMIC Module)
-- ============================================================
CREATE TABLE order_book_snapshots (
    id BIGSERIAL PRIMARY KEY,
    condition_id VARCHAR(66) REFERENCES markets(condition_id),

    -- Order Book State
    bids JSONB NOT NULL, -- [{price: 0.65, size: 1000}, ...]
    asks JSONB NOT NULL, -- [{price: 0.68, size: 500}, ...]

    -- Liquidity Metrics
    total_bid_liquidity DECIMAL(20,2),
    total_ask_liquidity DECIMAL(20,2),
    spread_bps INT, -- Basis points (1 bp = 0.01%)

    -- Spoofing Detection
    suspected_spoof_orders JSONB, -- Orders that appeared and disappeared quickly

    snapshot_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_orderbook_market ON order_book_snapshots(condition_id, snapshot_at DESC);
CREATE INDEX idx_orderbook_time ON order_book_snapshots(snapshot_at DESC);

-- ============================================================
-- TABLE: market_events (Event Timeline for Markets)
-- ============================================================
CREATE TABLE market_events (
    id BIGSERIAL PRIMARY KEY,
    condition_id VARCHAR(66) REFERENCES markets(condition_id),

    -- Event Details
    event_type VARCHAR(50) NOT NULL, -- 'PRICE_SPIKE', 'LIQUIDITY_DROP', 'VOLUME_SURGE'
    description TEXT,

    -- Metrics
    old_value DECIMAL(20,8),
    new_value DECIMAL(20,8),
    change_pct DECIMAL(10,4),

    -- Context
    metadata JSONB,

    occurred_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_market_events_market ON market_events(condition_id, occurred_at DESC);
CREATE INDEX idx_market_events_type ON market_events(event_type);

-- ============================================================
-- MATERIALIZED VIEW: Wallet Leaderboard
-- ============================================================
CREATE MATERIALIZED VIEW wallet_leaderboard AS
SELECT
    w.address,
    w.total_trades,
    w.total_volume_usd,
    w.total_pnl_usd,
    w.win_rate,
    wp.roi_pct,
    wp.copy_score,
    wp.insider_confidence_score,
    w.is_whale,
    w.is_suspected_insider,
    w.first_seen_at,
    w.last_active_at
FROM wallets w
LEFT JOIN wallet_profiles wp ON w.address = wp.wallet_address
WHERE w.total_trades >= 5
ORDER BY wp.copy_score DESC NULLS LAST;

CREATE UNIQUE INDEX idx_wallet_leaderboard_address ON wallet_leaderboard(address);

-- ============================================================
-- FUNCTION: Calculate Freshness Score
-- ============================================================
CREATE OR REPLACE FUNCTION calculate_freshness_score(wallet_first_seen TIMESTAMP)
RETURNS INT AS $$
DECLARE
    age_hours NUMERIC;
    score INT;
BEGIN
    age_hours := EXTRACT(EPOCH FROM (NOW() - wallet_first_seen)) / 3600;

    -- 100 = brand new (< 1 hour)
    -- 0 = ancient (> 1 year)
    IF age_hours < 1 THEN
        score := 100;
    ELSIF age_hours < 24 THEN
        score := 90;
    ELSIF age_hours < 168 THEN -- 1 week
        score := 70;
    ELSIF age_hours < 720 THEN -- 1 month
        score := 40;
    ELSIF age_hours < 8760 THEN -- 1 year
        score := 10;
    ELSE
        score := 0;
    END IF;

    RETURN score;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- TRIGGER: Auto-update wallet freshness score
-- ============================================================
CREATE OR REPLACE FUNCTION update_wallet_freshness()
RETURNS TRIGGER AS $$
BEGIN
    NEW.freshness_score := calculate_freshness_score(NEW.first_seen_at);
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_wallet_freshness
BEFORE INSERT OR UPDATE ON wallets
FOR EACH ROW
EXECUTE FUNCTION update_wallet_freshness();

-- ============================================================
-- End of Schema
-- ============================================================
