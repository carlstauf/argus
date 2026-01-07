"""
ARGUS Intelligence Engine v2.0
Advanced insider detection with:
- Composite Signal Scoring
- Time-to-Resolution Weighting
- Position Size Recommendations (Kelly Criterion)
- Wallet Profile Learning
- Resolution Outcome Tracking
"""

import os
import time
import asyncio
import psycopg2
import psycopg2.extras
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()


class IntelligenceEngine:
    """
    The Intelligence Engine v2.0: Real-time insider detection with profit optimization

    Detection Algorithms:
    1. Fresh Wallet Detection (burner wallets)
    2. The Hammer (order structuring)
    3. Unusual Sizing (outlier trades)
    4. Proven Winner Detection (follow smart money)
    
    Enhancements:
    - Composite Signal Scoring (multiple signals = higher confidence)
    - Time-to-Resolution Weighting (urgent markets prioritized)
    - Kelly Criterion Position Sizing
    - Outcome Tracking
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

        # Position sizing
        self.default_bankroll = float(os.getenv('DEFAULT_BANKROLL', 10000))
        self.max_position_pct = float(os.getenv('MAX_POSITION_PCT', 0.10))  # 10% max

        # Cache for market statistics (rolling averages)
        self.market_stats_cache = {}
        self.market_end_date_cache = {}
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
            List of alert dicts with composite scoring and position recommendations
        """
        alerts = []

        wallet_address = trade.get('wallet_address')
        condition_id = trade.get('condition_id')
        value_usd = trade.get('value_usd', 0)
        price = trade.get('price', 0.5)

        if not wallet_address or not condition_id:
            return alerts

        # Get market end date for time-to-resolution weighting
        end_date = await self._get_market_end_date(condition_id)
        hours_to_resolution = self._hours_until(end_date)
        urgency_multiplier = self._calculate_urgency_multiplier(hours_to_resolution)

        # Run all detection algorithms concurrently
        results = await asyncio.gather(
            self.detect_fresh_wallet(wallet_address, value_usd),
            self.detect_hammer_pattern(wallet_address, condition_id, value_usd),
            self.detect_unusual_sizing(condition_id, value_usd),
            self.detect_proven_winner(wallet_address, value_usd, condition_id),
            return_exceptions=True
        )

        # Collect triggered alerts
        triggered_alerts = []
        for result in results:
            if isinstance(result, dict) and result.get('alert'):
                # Apply time-to-resolution weighting
                base_confidence = result.get('confidence_score', 0.5)
                adjusted_confidence = min(base_confidence * urgency_multiplier, 0.99)
                
                result['wallet_address'] = wallet_address
                result['condition_id'] = condition_id
                result['urgency_multiplier'] = urgency_multiplier
                result['adjusted_confidence'] = adjusted_confidence
                result['hours_to_resolution'] = hours_to_resolution
                
                # Add position sizing recommendation
                result['position_recommendation'] = self._calculate_position_recommendation(
                    adjusted_confidence, price
                )
                
                triggered_alerts.append(result)

        # Check for composite (MEGA) signal
        if len(triggered_alerts) >= 2:
            mega_alert = self._create_composite_alert(
                triggered_alerts, wallet_address, condition_id, 
                hours_to_resolution, urgency_multiplier, price
            )
            alerts.append(mega_alert)
        
        # Add individual alerts
        alerts.extend(triggered_alerts)

        return alerts

    # ============================================================
    # Composite Signal Scoring
    # ============================================================

    def _create_composite_alert(
        self, 
        triggered_alerts: List[Dict], 
        wallet_address: str,
        condition_id: str,
        hours_to_resolution: float,
        urgency_multiplier: float,
        price: float
    ) -> Dict:
        """
        Create a MEGA SIGNAL alert when multiple detections trigger
        Combined confidence is calculated using independence assumption
        """
        composite_confidence = self._calculate_composite_score(triggered_alerts)
        
        # Get component types for display
        component_types = [a.get('alert_type', 'UNKNOWN') for a in triggered_alerts]
        component_titles = [a.get('title', '')[:50] for a in triggered_alerts]
        
        # Determine severity based on composite confidence
        if composite_confidence >= 0.95:
            severity = 'CRITICAL'
        elif composite_confidence >= 0.85:
            severity = 'HIGH'
        else:
            severity = 'MEDIUM'
        
        # Calculate position recommendation for composite
        position_rec = self._calculate_position_recommendation(composite_confidence, price)
        
        return {
            'alert': True,
            'alert_type': 'MEGA_SIGNAL',
            'severity': severity,
            'title': f'🔥 MEGA SIGNAL: {len(triggered_alerts)} detections triggered!',
            'description': f'Multiple insider signals detected simultaneously: {", ".join(component_types)}. Combined confidence: {composite_confidence*100:.1f}%.',
            'confidence_score': composite_confidence,
            'adjusted_confidence': composite_confidence,  # Already adjusted in components
            'wallet_address': wallet_address,
            'condition_id': condition_id,
            'hours_to_resolution': hours_to_resolution,
            'urgency_multiplier': urgency_multiplier,
            'is_composite': True,
            'component_types': component_types,
            'component_alerts': component_titles,
            'position_recommendation': position_rec,
            'supporting_data': {
                'num_signals': len(triggered_alerts),
                'component_types': component_types,
                'individual_confidences': [a.get('confidence_score', 0) for a in triggered_alerts],
                'composite_confidence': composite_confidence
            }
        }

    def _calculate_composite_score(self, alerts: List[Dict]) -> float:
        """
        Calculate combined confidence using independence assumption
        
        Formula: P(at least one correct) = 1 - ∏(1 - P_i)
        
        This gives higher confidence when multiple independent signals agree
        """
        if not alerts:
            return 0.0
        
        failure_prob = 1.0
        for alert in alerts:
            conf = alert.get('confidence_score', 0.5)
            failure_prob *= (1 - conf)
        
        return min(1 - failure_prob, 0.99)

    # ============================================================
    # Time-to-Resolution Weighting
    # ============================================================

    async def _get_market_end_date(self, condition_id: str) -> Optional[datetime]:
        """Get market end date from cache or database"""
        current_time = time.time()
        
        # Check cache
        if (condition_id in self.market_end_date_cache and
            current_time - self.last_cache_update.get(f'end_{condition_id}', 0) < self.cache_ttl):
            return self.market_end_date_cache[condition_id]
        
        try:
            cursor = self.db_conn.cursor()
            cursor.execute("""
                SELECT end_date FROM markets WHERE condition_id = %s
            """, (condition_id,))
            result = cursor.fetchone()
            cursor.close()
            
            end_date = result[0] if result else None
            self.market_end_date_cache[condition_id] = end_date
            self.last_cache_update[f'end_{condition_id}'] = current_time
            
            return end_date
        except Exception:
            return None

    def _hours_until(self, end_date: Optional[datetime]) -> float:
        """Calculate hours until market resolution"""
        if not end_date:
            return 168  # Default to 1 week if unknown
        
        now = datetime.now()
        if end_date <= now:
            return 0
        
        delta = end_date - now
        return delta.total_seconds() / 3600

    def _calculate_urgency_multiplier(self, hours_to_resolution: float) -> float:
        """
        Calculate urgency multiplier based on time to resolution
        
        Markets closing soon are more actionable
        """
        if hours_to_resolution <= 0:
            return 1.0  # Already resolved
        elif hours_to_resolution < 24:
            return 1.5  # URGENT - closing within 24h
        elif hours_to_resolution < 72:
            return 1.25  # HIGH - closing within 3 days
        elif hours_to_resolution < 168:
            return 1.1  # MEDIUM - closing within 1 week
        else:
            return 1.0  # NORMAL - more than 1 week out

    # ============================================================
    # Position Sizing (Kelly Criterion)
    # ============================================================

    def _calculate_position_recommendation(
        self, 
        confidence: float, 
        market_price: float,
        bankroll: float = None
    ) -> Dict:
        """
        Calculate recommended position size using Half-Kelly Criterion
        
        Kelly Formula: f* = (p*b - q) / b
        Where:
            p = probability of winning (confidence)
            q = probability of losing (1-p)
            b = odds received (1/price - 1)
            
        We use Half-Kelly for safety (reduces variance at cost of slower growth)
        """
        if bankroll is None:
            bankroll = self.default_bankroll
            
        if market_price <= 0 or market_price >= 1 or confidence <= 0:
            return {
                'recommended_size_usd': 0,
                'kelly_fraction': 0,
                'half_kelly_fraction': 0,
                'edge_pct': 0,
                'bankroll_assumed': bankroll,
                'explanation': 'Invalid price or confidence'
            }
        
        # Calculate edge and odds
        p = confidence  # Our estimated probability of winning
        q = 1 - p       # Probability of losing
        b = (1 / market_price) - 1  # Odds we're getting (e.g., price 0.4 = 1.5:1 odds)
        
        # Kelly formula
        if b <= 0:
            kelly = 0
        else:
            kelly = (p * b - q) / b
        
        # Use Half-Kelly for safety
        half_kelly = max(kelly / 2, 0)
        
        # Cap at max position percentage
        capped_fraction = min(half_kelly, self.max_position_pct)
        
        # Calculate recommended size
        recommended_size = bankroll * capped_fraction
        
        # Calculate edge over market
        edge_pct = (p - market_price) * 100  # How much better our estimate is than market
        
        # Generate explanation
        if edge_pct <= 0:
            explanation = 'No edge over market - consider skipping'
        elif capped_fraction < half_kelly:
            explanation = f'Position capped at {self.max_position_pct*100:.0f}% of bankroll'
        elif kelly > 0.25:
            explanation = 'Strong edge detected - high conviction bet'
        else:
            explanation = 'Moderate edge - standard position size'
        
        return {
            'recommended_size_usd': round(recommended_size, 2),
            'kelly_fraction': round(kelly, 4),
            'half_kelly_fraction': round(half_kelly, 4),
            'capped_fraction': round(capped_fraction, 4),
            'edge_pct': round(edge_pct, 2),
            'market_price': market_price,
            'our_probability': round(confidence, 4),
            'bankroll_assumed': bankroll,
            'explanation': explanation
        }

    # ============================================================
    # Detection Algorithm 1: Fresh Wallet (The Burner Check)
    # ============================================================

    async def detect_fresh_wallet(self, wallet_address: str, value_usd: float) -> Optional[Dict]:
        """
        Detect brand-new wallets making large bets

        Strategy:
        1. First check Polymarket API for wallet's TRUE first trade date
        2. If API check fails, fall back to database first_seen_at
        3. If < 72h old AND bet > $1k → CRITICAL ALERT

        IMPORTANT: We now verify wallet age via API to prevent false positives
        on old wallets that we just started tracking.

        Returns alert dict or None
        """

        # Only check if trade is significant
        if value_usd < self.fresh_wallet_min_usd:
            return None

        try:
            # STEP 1: Check Polymarket API for TRUE wallet history
            # This is the authoritative source - prevents false positives on old wallets
            from src.api.polymarket_client import PolymarketClient
            client = PolymarketClient()
            
            is_truly_fresh, api_age_hours = client.is_wallet_truly_fresh(
                wallet_address, 
                max_age_hours=self.fresh_wallet_hours
            )
            
            # If API says wallet is NOT fresh, don't alert (even if our DB says fresh)
            if not is_truly_fresh and api_age_hours > 0:
                # Update our database with the correct first_seen_at
                try:
                    first_trade_ts = client.get_wallet_first_trade_timestamp(wallet_address)
                    if first_trade_ts:
                        from datetime import datetime
                        first_trade_dt = datetime.fromtimestamp(first_trade_ts)
                        cursor = self.db_conn.cursor()
                        cursor.execute("""
                            UPDATE wallets 
                            SET first_seen_at = LEAST(first_seen_at, %s)
                            WHERE address = %s
                        """, (first_trade_dt, wallet_address))
                        self.db_conn.commit()
                        cursor.close()
                except Exception:
                    pass  # Don't fail on update
                    
                return None  # NOT a fresh wallet
            
            # STEP 2: If API confirms fresh (or couldn't check), get more details from DB
            cursor = self.db_conn.cursor()

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

            # Use API age if available, otherwise DB age
            if api_age_hours > 0:
                age_hours = api_age_hours
            elif result:
                age_hours = result[0]
            else:
                age_hours = 0  # Brand new
            
            total_trades = result[1] if result else 0
            total_volume = result[2] if result else 0

            if not result:
                # Wallet doesn't exist yet (will be created by ingestor)
                # API check passed or returned no history = truly new
                return {
                    'alert': True,
                    'alert_type': 'CRITICAL_FRESH',
                    'severity': 'CRITICAL',
                    'title': f'🚨 BURNER WALLET: ${value_usd:,.0f} from BRAND NEW wallet',
                    'description': f'Wallet {wallet_address[:10]}... has no trading history on Polymarket and immediately placed ${value_usd:,.0f} bet. Extremely high insider probability.',
                    'confidence_score': 0.95,
                    'supporting_data': {
                        'wallet_age_hours': 0,
                        'trade_value_usd': value_usd,
                        'is_first_trade': True,
                        'api_verified': True
                    }
                }

            # Fresh wallet check (double-confirmed by API)
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
                        'description': f'Wallet {wallet_address[:10]}... is only {age_hours:.1f}h old on Polymarket with {total_trades} trades totaling ${total_volume:,.0f}. New ${value_usd:,.0f} bet detected. API-verified fresh.',
                        'confidence_score': confidence,
                        'supporting_data': {
                            'wallet_age_hours': age_hours,
                            'trade_value_usd': value_usd,
                            'total_trades': total_trades,
                            'total_volume_usd': float(total_volume) if total_volume else 0,
                            'api_verified': True
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
    # Detection Algorithm 4: Proven Winner (Wallet Profile Learning)
    # ============================================================

    async def detect_proven_winner(
        self, wallet_address: str, value_usd: float, condition_id: str
    ) -> Optional[Dict]:
        """
        Alert when a historically accurate wallet makes a trade
        These wallets have been vetted by past performance
        
        Returns alert dict or None
        """
        # Lower threshold for proven winners
        if value_usd < 500:
            return None
            
        try:
            cursor = self.db_conn.cursor()
            
            cursor.execute("""
                SELECT 
                    wp.signal_accuracy,
                    wp.signals_generated,
                    wp.follow_priority,
                    w.total_pnl_usd,
                    w.win_rate,
                    w.total_trades
                FROM wallet_profiles wp
                JOIN wallets w ON wp.wallet_address = w.address
                WHERE 
                    wp.wallet_address = %s
                    AND wp.signal_accuracy >= 0.60  -- 60%+ accuracy
                    AND wp.signals_generated >= 3   -- Enough sample size
            """, (wallet_address,))
            
            result = cursor.fetchone()
            cursor.close()
            
            if result:
                accuracy, signals, priority, pnl, win_rate, total_trades = result
                
                # Boost confidence based on track record
                base_confidence = float(accuracy) if accuracy else 0.6
                
                # Priority wallets get extra boost
                if priority == 'PRIORITY':
                    base_confidence = min(base_confidence * 1.15, 0.95)
                
                severity = 'HIGH' if base_confidence >= 0.75 else 'MEDIUM'
                
                return {
                    'alert': True,
                    'alert_type': 'PROVEN_WINNER',
                    'severity': severity,
                    'title': f'⭐ PROVEN WINNER: {accuracy*100:.0f}% accurate wallet trading ${value_usd:,.0f}',
                    'description': f'Wallet {wallet_address[:10]}... has {accuracy*100:.0f}% historical signal accuracy over {signals} tracked signals. Lifetime P&L: ${pnl:,.0f}.',
                    'confidence_score': base_confidence,
                    'supporting_data': {
                        'historical_accuracy': float(accuracy) if accuracy else 0,
                        'signals_tracked': signals,
                        'follow_priority': priority,
                        'lifetime_pnl_usd': float(pnl) if pnl else 0,
                        'win_rate': float(win_rate) if win_rate else 0,
                        'total_trades': total_trades
                    }
                }
                
        except Exception as e:
            # Silent fail - table might not exist yet
            pass
            
        return None

    # ============================================================
    # Alert Persistence
    # ============================================================

    def save_alert(self, alert: Dict) -> bool:
        """
        Save alert to database with all v2.0 fields

        Args:
            alert: Alert dict with all required fields

        Returns:
            True if saved successfully
        """
        try:
            cursor = self.db_conn.cursor()

            # Get position recommendation data
            pos_rec = alert.get('position_recommendation', {})
            
            cursor.execute("""
                INSERT INTO alerts (
                    alert_type, severity, wallet_address, condition_id,
                    title, description, confidence_score, supporting_data,
                    adjusted_confidence, hours_to_resolution,
                    recommended_size_usd, kelly_fraction,
                    is_composite, component_types
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                alert.get('alert_type'),
                alert.get('severity'),
                alert.get('wallet_address'),
                alert.get('condition_id'),
                alert.get('title'),
                alert.get('description'),
                alert.get('confidence_score'),
                psycopg2.extras.Json(alert.get('supporting_data', {})),
                alert.get('adjusted_confidence'),
                alert.get('hours_to_resolution'),
                pos_rec.get('recommended_size_usd'),
                pos_rec.get('kelly_fraction'),
                alert.get('is_composite', False),
                psycopg2.extras.Json(alert.get('component_types')) if alert.get('component_types') else None
            ))

            self.db_conn.commit()
            cursor.close()

            return True

        except Exception as e:
            self.db_conn.rollback()
            return False

    # ============================================================
    # Performance Tracking (Resolution Outcomes)
    # ============================================================

    async def update_alert_outcomes(self):
        """
        Update alert outcomes when markets resolve
        Call this periodically (e.g., every hour)
        """
        try:
            cursor = self.db_conn.cursor()
            
            # Find alerts with pending outcomes where market has resolved
            cursor.execute("""
                SELECT 
                    a.id, a.condition_id, a.supporting_data, 
                    a.confidence_score, m.resolution
                FROM alerts a
                JOIN markets m ON a.condition_id = m.condition_id
                WHERE 
                    a.market_resolution IS NULL
                    AND m.resolution IS NOT NULL
            """)
            
            rows = cursor.fetchall()
            
            for alert_id, condition_id, data, confidence, resolution in rows:
                # Determine what side the alert suggested
                # Default to 'Yes' if not specified
                if data and isinstance(data, dict):
                    outcome_bet = data.get('outcome', 'Yes')
                else:
                    outcome_bet = 'Yes'
                
                # Normalize comparison
                was_profitable = (outcome_bet.upper() == resolution.upper())
                
                # Calculate hypothetical P&L (assume $100 bet at market price)
                if data and isinstance(data, dict):
                    entry_price = data.get('price', 0.5)
                else:
                    entry_price = 0.5
                    
                if was_profitable:
                    # Won: $100 bet at entry_price returns $100/entry_price
                    pnl = 100 * (1/entry_price - 1) if entry_price > 0 else 0
                else:
                    # Lost: lose the $100 bet
                    pnl = -100
                
                cursor.execute("""
                    UPDATE alerts SET
                        market_resolution = %s,
                        was_profitable = %s,
                        hypothetical_pnl_usd = %s,
                        resolved_at = NOW()
                    WHERE id = %s
                """, (resolution, was_profitable, pnl, alert_id))
            
            self.db_conn.commit()
            cursor.close()
            
            return len(rows)
            
        except Exception as e:
            self.db_conn.rollback()
            return 0

    async def compute_signal_performance(self):
        """
        Aggregate performance metrics per alert type
        Call this periodically (e.g., daily)
        """
        try:
            cursor = self.db_conn.cursor()
            
            cursor.execute("""
                INSERT INTO signal_performance (
                    alert_type, total_signals, profitable_signals, win_rate,
                    avg_confidence_score, total_hypothetical_pnl, avg_hours_to_resolution
                )
                SELECT
                    alert_type,
                    COUNT(*) as total_signals,
                    SUM(CASE WHEN was_profitable THEN 1 ELSE 0 END) as profitable_signals,
                    AVG(CASE WHEN was_profitable THEN 1.0 ELSE 0.0 END) as win_rate,
                    AVG(confidence_score) as avg_confidence_score,
                    SUM(hypothetical_pnl_usd) as total_hypothetical_pnl,
                    AVG(hours_to_resolution) as avg_hours_to_resolution
                FROM alerts
                WHERE 
                    market_resolution IS NOT NULL
                    AND resolved_at >= NOW() - INTERVAL '30 days'
                GROUP BY alert_type
                ON CONFLICT (alert_type) DO UPDATE SET
                    total_signals = EXCLUDED.total_signals,
                    profitable_signals = EXCLUDED.profitable_signals,
                    win_rate = EXCLUDED.win_rate,
                    avg_confidence_score = EXCLUDED.avg_confidence_score,
                    total_hypothetical_pnl = EXCLUDED.total_hypothetical_pnl,
                    avg_hours_to_resolution = EXCLUDED.avg_hours_to_resolution,
                    computed_at = NOW()
            """)
            
            self.db_conn.commit()
            cursor.close()
            
            return True
            
        except Exception as e:
            self.db_conn.rollback()
            return False

    async def update_wallet_signal_accuracy(self):
        """
        Update wallet profiles with their signal accuracy
        Call this periodically (e.g., daily)
        """
        try:
            cursor = self.db_conn.cursor()
            
            # Calculate per-wallet signal performance
            cursor.execute("""
                WITH wallet_stats AS (
                    SELECT
                        wallet_address,
                        COUNT(*) as signals_generated,
                        SUM(CASE WHEN was_profitable THEN 1 ELSE 0 END) as signals_profitable,
                        AVG(CASE WHEN was_profitable THEN 1.0 ELSE 0.0 END) as signal_accuracy
                    FROM alerts
                    WHERE 
                        market_resolution IS NOT NULL
                        AND wallet_address IS NOT NULL
                    GROUP BY wallet_address
                )
                UPDATE wallet_profiles wp SET
                    signal_accuracy = ws.signal_accuracy,
                    signals_generated = ws.signals_generated,
                    signals_profitable = ws.signals_profitable,
                    follow_priority = CASE 
                        WHEN ws.signal_accuracy >= 0.70 AND ws.signals_generated >= 5 THEN 'PRIORITY'
                        WHEN ws.signal_accuracy < 0.40 AND ws.signals_generated >= 5 THEN 'IGNORE'
                        ELSE 'NORMAL'
                    END,
                    updated_at = NOW()
                FROM wallet_stats ws
                WHERE wp.wallet_address = ws.wallet_address
            """)
            
            self.db_conn.commit()
            cursor.close()
            
            return True
            
        except Exception as e:
            self.db_conn.rollback()
            return False
