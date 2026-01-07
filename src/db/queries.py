"""
ARGUS - Intelligence Queries
Pre-built queries for the PANOPTICON surveillance system
"""

from typing import List, Dict, Any

class IntelligenceQueries:
    """SQL queries for detecting anomalies and insider activity"""

    @staticmethod
    def fresh_wallets_with_large_bets(hours: int = 24, min_usd: float = 5000) -> str:
        """
        Q1: Detect Fresh Wallets with Big Bets
        Returns wallets that are < N hours old and made bets > $X
        This is the #1 insider signal.
        """
        return f"""
        SELECT
            t.wallet_address,
            w.first_seen_at,
            EXTRACT(EPOCH FROM (t.executed_at - w.first_seen_at))/3600 AS wallet_age_hours,
            t.value_usd,
            t.side,
            t.outcome,
            t.condition_id,
            m.question,
            m.category,
            w.freshness_score
        FROM trades t
        JOIN wallets w ON t.wallet_address = w.address
        JOIN markets m ON t.condition_id = m.condition_id
        WHERE
            EXTRACT(EPOCH FROM (t.executed_at - w.first_seen_at)) < {hours * 3600}
            AND t.value_usd > {min_usd}
        ORDER BY t.executed_at DESC
        LIMIT 50;
        """

    @staticmethod
    def insider_trading_pattern() -> str:
        """
        Q2: Detect Insider Trading Pattern
        Finds wallets that consistently trade BEFORE news breaks
        """
        return """
        SELECT
            t.wallet_address,
            COUNT(*) as suspicious_trades,
            AVG(t.news_distance_seconds) as avg_seconds_before_news,
            SUM(t.value_usd) as total_value_usd,
            w.win_rate,
            wp.insider_confidence_score
        FROM trades t
        JOIN wallets w ON t.wallet_address = w.address
        LEFT JOIN wallet_profiles wp ON t.wallet_address = wp.wallet_address
        WHERE
            t.news_distance_seconds < 0  -- Trade happened BEFORE news
            AND ABS(t.news_distance_seconds) < 3600  -- Within 1 hour
        GROUP BY t.wallet_address, w.win_rate, wp.insider_confidence_score
        HAVING COUNT(*) >= 3
        ORDER BY suspicious_trades DESC, avg_seconds_before_news ASC
        LIMIT 100;
        """

    @staticmethod
    def copy_leaderboard(min_trades: int = 10) -> str:
        """
        Q3: The Copy Leaderboard
        Ranks wallets by profitability and timing patterns
        """
        return f"""
        SELECT
            wp.wallet_address,
            w.total_trades,
            w.total_volume_usd,
            w.total_pnl_usd,
            w.win_rate,
            wp.roi_pct,
            wp.sharpe_ratio,
            wp.copy_score,
            wp.avg_time_before_resolution_hours,
            w.last_active_at,
            CASE
                WHEN wp.avg_time_before_resolution_hours < 24 THEN 'SNIPER'
                WHEN wp.avg_time_before_resolution_hours < 168 THEN 'TACTICAL'
                ELSE 'STRATEGIC'
            END as trader_type
        FROM wallet_profiles wp
        JOIN wallets w ON wp.wallet_address = w.address
        WHERE
            w.total_trades >= {min_trades}
            AND w.win_rate > 0.55
        ORDER BY wp.copy_score DESC
        LIMIT 50;
        """

    @staticmethod
    def whale_movements(min_usd: float = 10000, hours: int = 24) -> str:
        """
        Q4: Recent Whale Movements
        Tracks large positions by known whales
        """
        return f"""
        SELECT
            t.wallet_address,
            t.executed_at,
            t.side,
            t.outcome,
            t.value_usd,
            t.condition_id,
            m.question,
            m.current_yes_price,
            m.current_no_price,
            w.total_pnl_usd as wallet_lifetime_pnl
        FROM trades t
        JOIN wallets w ON t.wallet_address = w.address
        JOIN markets m ON t.condition_id = m.condition_id
        WHERE
            w.is_whale = TRUE
            AND t.value_usd >= {min_usd}
            AND t.executed_at > NOW() - INTERVAL '{hours} hours'
        ORDER BY t.executed_at DESC, t.value_usd DESC
        LIMIT 100;
        """

    @staticmethod
    def anomalous_trades(sigma: float = 2.0, hours: int = 24) -> str:
        """
        Q5: Detect Statistical Anomalies
        Finds trades that are > N standard deviations from the mean
        """
        return f"""
        WITH trade_stats AS (
            SELECT
                condition_id,
                AVG(value_usd) as avg_value,
                STDDEV(value_usd) as stddev_value
            FROM trades
            WHERE executed_at > NOW() - INTERVAL '7 days'
            GROUP BY condition_id
        )
        SELECT
            t.wallet_address,
            t.executed_at,
            t.condition_id,
            m.question,
            t.value_usd,
            ts.avg_value,
            ts.stddev_value,
            (t.value_usd - ts.avg_value) / NULLIF(ts.stddev_value, 0) as sigma_distance
        FROM trades t
        JOIN markets m ON t.condition_id = m.condition_id
        JOIN trade_stats ts ON t.condition_id = ts.condition_id
        WHERE
            t.executed_at > NOW() - INTERVAL '{hours} hours'
            AND t.is_anomalous = TRUE
            AND ts.stddev_value > 0
            AND ABS((t.value_usd - ts.avg_value) / ts.stddev_value) > {sigma}
        ORDER BY sigma_distance DESC
        LIMIT 50;
        """

    @staticmethod
    def reality_gap_opportunities() -> str:
        """
        Q6: Reality Gap Detection
        Finds markets where news sentiment doesn't match market odds
        """
        return """
        WITH market_prices AS (
            SELECT
                condition_id,
                current_yes_price,
                current_no_price
            FROM markets
            WHERE status = 'ACTIVE'
        ),
        recent_news AS (
            SELECT DISTINCT ON (ne.id)
                ne.id,
                ne.headline,
                ne.sentiment_score,
                ne.confidence_score,
                ne.published_at,
                jsonb_array_elements_text(ne.related_condition_ids)::varchar as condition_id
            FROM news_events ne
            WHERE
                ne.published_at > NOW() - INTERVAL '6 hours'
                AND ne.confidence_score > 0.75
        )
        SELECT
            rn.headline,
            rn.sentiment_score,
            rn.confidence_score,
            mp.current_yes_price,
            mp.current_no_price,
            ABS(rn.sentiment_score - mp.current_yes_price) as gap_size,
            CASE
                WHEN rn.sentiment_score > 0.8 AND mp.current_yes_price < 0.6 THEN 'BUY_YES'
                WHEN rn.sentiment_score < 0.2 AND mp.current_no_price < 0.6 THEN 'BUY_NO'
                ELSE 'MONITOR'
            END as signal,
            rn.condition_id,
            m.question
        FROM recent_news rn
        JOIN market_prices mp ON rn.condition_id = mp.condition_id
        JOIN markets m ON rn.condition_id = m.condition_id
        WHERE
            ABS(rn.sentiment_score - mp.current_yes_price) > 0.20
        ORDER BY gap_size DESC
        LIMIT 25;
        """

    @staticmethod
    def wallet_activity_timeline(wallet_address: str, days: int = 30) -> str:
        """
        Q7: Wallet Activity Timeline
        Full trade history and pattern analysis for a specific wallet
        """
        return f"""
        SELECT
            t.executed_at,
            t.side,
            t.outcome,
            t.value_usd,
            t.price,
            m.question,
            m.category,
            m.resolution,
            CASE
                WHEN m.resolution IS NOT NULL THEN
                    CASE
                        WHEN (t.outcome = m.resolution AND t.side = 'BUY')
                            OR (t.outcome != m.resolution AND t.side = 'SELL')
                        THEN 'WIN'
                        ELSE 'LOSS'
                    END
                ELSE 'PENDING'
            END as trade_result
        FROM trades t
        JOIN markets m ON t.condition_id = m.condition_id
        WHERE
            t.wallet_address = '{wallet_address}'
            AND t.executed_at > NOW() - INTERVAL '{days} days'
        ORDER BY t.executed_at DESC;
        """
