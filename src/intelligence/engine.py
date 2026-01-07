"""
ARGUS Intelligence Engine
Advanced insider detection algorithms
"""

import os
import time
import asyncio
import psycopg2
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()


class IntelligenceEngine:
    """
    The Intelligence Engine: Real-time insider detection

    Detects three types of insider behavior:
    1. Fresh Wallet Detection (burner wallets)
    2. The Hammer (order structuring)
    3. Unusual Sizing (outlier trades)
    """

    def __init__(self, db_conn):
        self.db_conn = db_conn

        # Thresholds from config
        self.fresh_wallet_hours = float(os.getenv('FRESH_WALLET_HOURS', 72))
        self.fresh_wallet_min_usd = float(os.getenv('WHALE_THRESHOLD_USD', 1000))

        # Hammer detection
        self.hammer_lookback_minutes = 60
        self.hammer_min_trades = 4
        self.hammer_min_volume = 2000

        # Unusual sizing
        self.unusual_sizing_multiplier = 3.0

        # Cache for market statistics (rolling averages)
        self.market_stats_cache = {}
        self.cache_ttl = 300  # 5 minutes
        self.last_cache_update = {}

    # ============================================================
    # Main Analysis Entry Point
    # ============================================================

    async def analyze(self, trade: Dict) -> List[Dict]:
        """
        Analyze a trade against all detection rules
        Returns list of alerts to create

        Args:
            trade: Trade dict with keys: wallet_address, condition_id, value_usd, timestamp, etc.

        Returns:
            List of alert dicts
        """
        alerts = []

        wallet_address = trade.get('wallet_address')
        condition_id = trade.get('condition_id')
        value_usd = trade.get('value_usd', 0)

        if not wallet_address or not condition_id:
            return alerts

        # Run all detection algorithms concurrently
        results = await asyncio.gather(
            self.detect_fresh_wallet(wallet_address, value_usd),
            self.detect_hammer_pattern(wallet_address, condition_id, value_usd),
            self.detect_unusual_sizing(condition_id, value_usd),
            return_exceptions=True
        )

        # Collect alerts from all detectors
        for result in results:
            if isinstance(result, dict) and result.get('alert'):
                alerts.append({
                    'wallet_address': wallet_address,
                    'condition_id': condition_id,
                    **result
                })

        return alerts

    # ============================================================
    # Detection Algorithm 1: Fresh Wallet (The Burner Check)
    # ============================================================

    async def detect_fresh_wallet(self, wallet_address: str, value_usd: float) -> Optional[Dict]:
        """
        Detect brand-new wallets making large bets

        Strategy:
        1. Check if wallet exists in our database
        2. If not, it's fresh → check age from database first_seen_at
        3. If < 72h old AND bet > $1k → CRITICAL ALERT

        Returns alert dict or None
        """

        # Only check if trade is significant
        if value_usd < self.fresh_wallet_min_usd:
            return None

        try:
            cursor = self.db_conn.cursor()

            # Get wallet age
            cursor.execute("""
                SELECT
                    EXTRACT(EPOCH FROM (NOW() - first_seen_at)) / 3600 as age_hours,
                    total_trades,
                    total_volume_usd
                FROM wallets
                WHERE address = %s
            """, (wallet_address,))

            result = cursor.fetchone()
            cursor.close()

            if not result:
                # Wallet doesn't exist yet (will be created by ingestor)
                # Assume it's brand new
                return {
                    'alert': True,
                    'alert_type': 'CRITICAL_FRESH',
                    'severity': 'CRITICAL',
                    'title': f'🚨 BURNER WALLET: ${value_usd:,.0f} from BRAND NEW wallet',
                    'description': f'Wallet {wallet_address[:10]}... just created and immediately placed ${value_usd:,.0f} bet. Extremely high insider probability.',
                    'confidence_score': 0.95,
                    'supporting_data': {
                        'wallet_age_hours': 0,
                        'trade_value_usd': value_usd,
                        'is_first_trade': True
                    }
                }

            age_hours, total_trades, total_volume = result

            # Fresh wallet check
            if age_hours < self.fresh_wallet_hours:
                confidence = self._calculate_freshness_confidence(
                    age_hours, value_usd, total_trades, total_volume
                )

                if confidence >= 0.70:
                    severity = 'CRITICAL' if confidence >= 0.85 else 'HIGH'

                    return {
                        'alert': True,
                        'alert_type': 'CRITICAL_FRESH',
                        'severity': severity,
                        'title': f'🚨 FRESH WALLET: ${value_usd:,.0f} from {age_hours:.1f}h old wallet',
                        'description': f'Wallet {wallet_address[:10]}... is only {age_hours:.1f}h old with {total_trades} trades totaling ${total_volume:,.0f}. New ${value_usd:,.0f} bet detected.',
                        'confidence_score': confidence,
                        'supporting_data': {
                            'wallet_age_hours': age_hours,
                            'trade_value_usd': value_usd,
                            'total_trades': total_trades,
                            'total_volume_usd': float(total_volume) if total_volume else 0
                        }
                    }

        except Exception as e:
            # Silent fail
            pass

        return None

    def _calculate_freshness_confidence(
        self, age_hours: float, value_usd: float, total_trades: int, total_volume: float
    ) -> float:
        """Calculate confidence score for fresh wallet alert"""

        confidence = 0.5  # Base

        # Age factor (fresher = higher confidence)
        if age_hours < 1:
            confidence += 0.3
        elif age_hours < 12:
            confidence += 0.2
        elif age_hours < 24:
            confidence += 0.1

        # Size factor (bigger = higher confidence)
        if value_usd > 10000:
            confidence += 0.2
        elif value_usd > 5000:
            confidence += 0.15
        elif value_usd > 2000:
            confidence += 0.1

        # First trade bonus
        if total_trades == 0:
            confidence += 0.15

        # Large percentage of total volume
        if total_volume > 0 and value_usd / total_volume > 0.5:
            confidence += 0.1

        return min(confidence, 0.99)

    # ============================================================
    # Detection Algorithm 2: The Hammer (Order Structuring)
    # ============================================================

    async def detect_hammer_pattern(
        self, wallet_address: str, condition_id: str, value_usd: float
    ) -> Optional[Dict]:
        """
        Detect order structuring (splitting large orders into small chunks)

        Strategy:
        1. Check recent trades (last 60 min) from this wallet on this market
        2. If > 4 trades AND total volume > $2k → SUSPICIOUS

        Returns alert dict or None
        """

        try:
            cursor = self.db_conn.cursor()

            # Get recent trades from this wallet on this market
            lookback = datetime.now() - timedelta(minutes=self.hammer_lookback_minutes)

            cursor.execute("""
                SELECT
                    COUNT(*) as trade_count,
                    SUM(value_usd) as total_volume,
                    AVG(value_usd) as avg_trade_size,
                    MIN(executed_at) as first_trade,
                    MAX(executed_at) as last_trade
                FROM trades
                WHERE
                    wallet_address = %s
                    AND condition_id = %s
                    AND executed_at >= %s
            """, (wallet_address, condition_id, lookback))

            result = cursor.fetchone()
            cursor.close()

            if not result:
                return None

            trade_count, total_volume, avg_trade_size, first_trade, last_trade = result

            # Check thresholds
            if (trade_count >= self.hammer_min_trades and
                total_volume >= self.hammer_min_volume):

                # Calculate time span
                time_span_minutes = (last_trade - first_trade).total_seconds() / 60

                confidence = self._calculate_hammer_confidence(
                    trade_count, total_volume, avg_trade_size, time_span_minutes
                )

                if confidence >= 0.60:
                    return {
                        'alert': True,
                        'alert_type': 'SUSPICIOUS_STRUCTURING',
                        'severity': 'HIGH',
                        'title': f'🔨 THE HAMMER: {trade_count} trades totaling ${total_volume:,.0f} in {time_span_minutes:.0f}min',
                        'description': f'Wallet {wallet_address[:10]}... executed {trade_count} trades on the same market in {time_span_minutes:.0f} minutes, totaling ${total_volume:,.0f}. Possible order structuring to hide large position.',
                        'confidence_score': confidence,
                        'supporting_data': {
                            'trade_count': trade_count,
                            'total_volume_usd': float(total_volume),
                            'avg_trade_size_usd': float(avg_trade_size),
                            'time_span_minutes': time_span_minutes
                        }
                    }

        except Exception as e:
            # Silent fail
            pass

        return None

    def _calculate_hammer_confidence(
        self, trade_count: int, total_volume: float, avg_trade_size: float, time_span_minutes: float
    ) -> float:
        """Calculate confidence score for hammer pattern"""

        confidence = 0.5  # Base

        # More trades = higher confidence
        if trade_count >= 10:
            confidence += 0.2
        elif trade_count >= 7:
            confidence += 0.15
        elif trade_count >= 5:
            confidence += 0.1

        # Higher volume = higher confidence
        if total_volume > 10000:
            confidence += 0.15
        elif total_volume > 5000:
            confidence += 0.1

        # Faster execution = higher confidence (more suspicious)
        if time_span_minutes < 10:
            confidence += 0.15
        elif time_span_minutes < 30:
            confidence += 0.1

        # Consistent sizing (low variance) = more suspicious
        # If all trades are similar size, it's more likely intentional structuring
        # This is a simple heuristic - could be improved

        return min(confidence, 0.95)

    # ============================================================
    # Detection Algorithm 3: Unusual Sizing (Outlier Detection)
    # ============================================================

    async def detect_unusual_sizing(self, condition_id: str, value_usd: float) -> Optional[Dict]:
        """
        Detect trades that are unusually large for a specific market

        Strategy:
        1. Get average trade size for this market
        2. If new trade is > 3x average → WHALE ANOMALY

        Returns alert dict or None
        """

        try:
            # Check cache first
            current_time = time.time()

            if (condition_id in self.market_stats_cache and
                current_time - self.last_cache_update.get(condition_id, 0) < self.cache_ttl):
                # Use cached stats
                avg_trade_size, stddev_trade_size, trade_count = self.market_stats_cache[condition_id]
            else:
                # Fetch fresh stats
                cursor = self.db_conn.cursor()

                cursor.execute("""
                    SELECT
                        AVG(value_usd) as avg_size,
                        STDDEV(value_usd) as stddev_size,
                        COUNT(*) as trade_count
                    FROM trades
                    WHERE
                        condition_id = %s
                        AND executed_at >= NOW() - INTERVAL '7 days'
                """, (condition_id,))

                result = cursor.fetchone()
                cursor.close()

                if not result or result[0] is None:
                    return None

                avg_trade_size, stddev_trade_size, trade_count = result
                avg_trade_size = float(avg_trade_size)
                stddev_trade_size = float(stddev_trade_size) if stddev_trade_size else 0

                # Update cache
                self.market_stats_cache[condition_id] = (avg_trade_size, stddev_trade_size, trade_count)
                self.last_cache_update[condition_id] = current_time

            # Need at least 10 trades to establish a baseline
            if trade_count < 10:
                return None

            # Calculate multiplier
            multiplier = value_usd / avg_trade_size if avg_trade_size > 0 else 0

            # Check if unusual
            if multiplier >= self.unusual_sizing_multiplier:

                # Calculate sigma distance (if we have stddev)
                sigma_distance = 0
                if stddev_trade_size > 0:
                    sigma_distance = (value_usd - avg_trade_size) / stddev_trade_size

                confidence = self._calculate_sizing_confidence(
                    multiplier, sigma_distance, avg_trade_size, trade_count
                )

                if confidence >= 0.60:
                    severity = 'HIGH' if multiplier >= 5 else 'MEDIUM'

                    return {
                        'alert': True,
                        'alert_type': 'WHALE_ANOMALY',
                        'severity': severity,
                        'title': f'📊 UNUSUAL SIZE: ${value_usd:,.0f} ({multiplier:.1f}x market avg)',
                        'description': f'Trade of ${value_usd:,.0f} is {multiplier:.1f}x the average trade size (${avg_trade_size:,.0f}) for this market. Possible whale or insider.',
                        'confidence_score': confidence,
                        'supporting_data': {
                            'trade_value_usd': value_usd,
                            'market_avg_trade_size': avg_trade_size,
                            'multiplier': multiplier,
                            'sigma_distance': sigma_distance,
                            'market_trade_count': trade_count
                        }
                    }

        except Exception as e:
            # Silent fail
            pass

        return None

    def _calculate_sizing_confidence(
        self, multiplier: float, sigma_distance: float, avg_trade_size: float, trade_count: int
    ) -> float:
        """Calculate confidence score for unusual sizing"""

        confidence = 0.5  # Base

        # Higher multiplier = higher confidence
        if multiplier >= 10:
            confidence += 0.3
        elif multiplier >= 5:
            confidence += 0.2
        elif multiplier >= 3:
            confidence += 0.1

        # Sigma distance
        if sigma_distance >= 5:
            confidence += 0.2
        elif sigma_distance >= 3:
            confidence += 0.15

        # More market data = higher confidence in the baseline
        if trade_count >= 100:
            confidence += 0.1
        elif trade_count >= 50:
            confidence += 0.05

        return min(confidence, 0.90)

    # ============================================================
    # Alert Persistence
    # ============================================================

    def save_alert(self, alert: Dict) -> bool:
        """
        Save alert to database

        Args:
            alert: Alert dict with all required fields

        Returns:
            True if saved successfully
        """
        try:
            cursor = self.db_conn.cursor()

            cursor.execute("""
                INSERT INTO alerts (
                    alert_type, severity, wallet_address, condition_id,
                    title, description, confidence_score, supporting_data
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                alert.get('alert_type'),
                alert.get('severity'),
                alert.get('wallet_address'),
                alert.get('condition_id'),
                alert.get('title'),
                alert.get('description'),
                alert.get('confidence_score'),
                psycopg2.extras.Json(alert.get('supporting_data', {}))
            ))

            self.db_conn.commit()
            cursor.close()

            return True

        except Exception as e:
            self.db_conn.rollback()
            return False
