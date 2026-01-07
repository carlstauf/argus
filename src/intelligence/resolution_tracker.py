"""
ARGUS Resolution Tracker
Background job for tracking market outcomes and updating signal performance

Run this periodically (recommended: hourly via cron or scheduler)

Usage:
    python -m src.intelligence.resolution_tracker
    
Or call from code:
    from src.intelligence.resolution_tracker import ResolutionTracker
    tracker = ResolutionTracker()
    await tracker.run_all_updates()
"""

import os
import asyncio
import psycopg2
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()


class ResolutionTracker:
    """
    Background job that:
    1. Polls Polymarket for market resolutions
    2. Updates alert outcomes (was_profitable, hypothetical_pnl)
    3. Computes aggregate signal performance metrics
    4. Updates wallet profile signal accuracy
    
    This creates a feedback loop that allows the system to learn
    which signals actually make money over time.
    """
    
    def __init__(self, db_conn=None):
        if db_conn:
            self.db_conn = db_conn
        else:
            database_url = os.getenv('DATABASE_URL')
            self.db_conn = psycopg2.connect(database_url)
    
    def close(self):
        if self.db_conn:
            self.db_conn.close()
    
    # ============================================================
    # Market Resolution Polling
    # ============================================================
    
    async def poll_market_resolutions(self) -> int:
        """
        Poll Polymarket for newly resolved markets and update database
        
        Returns number of markets updated
        """
        from src.api.polymarket_client import PolymarketClient
        
        client = PolymarketClient()
        updated_count = 0
        
        try:
            cursor = self.db_conn.cursor()
            
            # Get markets that are past their end_date but not yet resolved
            cursor.execute("""
                SELECT condition_id, slug
                FROM markets
                WHERE 
                    status = 'ACTIVE'
                    AND end_date IS NOT NULL
                    AND end_date < NOW()
                    AND resolution IS NULL
                LIMIT 50
            """)
            
            markets_to_check = cursor.fetchall()
            
            for condition_id, slug in markets_to_check:
                try:
                    # Fetch market data from API
                    if slug:
                        market_data = client.get_market_by_slug(slug)
                    else:
                        market_data = client.get_market_by_id(condition_id)
                    
                    if market_data:
                        # Check if resolved
                        resolution = market_data.get('resolution')
                        resolved = market_data.get('resolved', False)
                        
                        if resolved and resolution:
                            cursor.execute("""
                                UPDATE markets SET
                                    resolution = %s,
                                    status = 'RESOLVED',
                                    resolved_at = NOW(),
                                    updated_at = NOW()
                                WHERE condition_id = %s
                            """, (resolution, condition_id))
                            
                            updated_count += 1
                            
                except Exception as e:
                    # Skip individual market errors
                    continue
            
            self.db_conn.commit()
            cursor.close()
            
        except Exception as e:
            self.db_conn.rollback()
            print(f"Error polling resolutions: {e}")
        
        return updated_count
    
    # ============================================================
    # Alert Outcome Tracking
    # ============================================================
    
    async def update_alert_outcomes(self) -> int:
        """
        Update alert outcomes when markets resolve
        
        For each alert on a resolved market:
        1. Determine if the signaled trade was profitable
        2. Calculate hypothetical P&L (as if $100 was bet)
        3. Update the alert record
        
        Returns number of alerts updated
        """
        try:
            cursor = self.db_conn.cursor()
            
            # Find alerts with pending outcomes where market has resolved
            cursor.execute("""
                SELECT 
                    a.id, 
                    a.condition_id, 
                    a.supporting_data, 
                    a.confidence_score,
                    a.alert_type,
                    m.resolution
                FROM alerts a
                JOIN markets m ON a.condition_id = m.condition_id
                WHERE 
                    a.market_resolution IS NULL
                    AND m.resolution IS NOT NULL
            """)
            
            rows = cursor.fetchall()
            updated_count = 0
            
            for alert_id, condition_id, data, confidence, alert_type, resolution in rows:
                try:
                    # Determine what side the alert suggested
                    # For most alerts, we assume they're signaling the "Yes" side
                    # unless the supporting_data specifies otherwise
                    if data and isinstance(data, dict):
                        outcome_bet = data.get('outcome', 'Yes')
                        entry_price = data.get('price', 0.5)
                    else:
                        outcome_bet = 'Yes'
                        entry_price = 0.5
                    
                    # Normalize comparison (both to uppercase)
                    resolution_normalized = resolution.upper() if resolution else ''
                    outcome_normalized = outcome_bet.upper() if outcome_bet else 'YES'
                    
                    was_profitable = (outcome_normalized == resolution_normalized)
                    
                    # Calculate hypothetical P&L
                    # Assume $100 bet at the entry price
                    if was_profitable:
                        # Won: profit = stake * (1/price - 1)
                        # e.g., $100 at 0.4 price → returns $250 → profit = $150
                        if entry_price > 0 and entry_price < 1:
                            pnl = 100 * (1/entry_price - 1)
                        else:
                            pnl = 100  # Default profit if price is weird
                    else:
                        # Lost: lose the entire stake
                        pnl = -100
                    
                    cursor.execute("""
                        UPDATE alerts SET
                            market_resolution = %s,
                            was_profitable = %s,
                            hypothetical_pnl_usd = %s,
                            resolved_at = NOW()
                        WHERE id = %s
                    """, (resolution, was_profitable, round(pnl, 2), alert_id))
                    
                    updated_count += 1
                    
                except Exception as e:
                    # Skip individual alert errors
                    continue
            
            self.db_conn.commit()
            cursor.close()
            
            return updated_count
            
        except Exception as e:
            self.db_conn.rollback()
            print(f"Error updating alert outcomes: {e}")
            return 0
    
    # ============================================================
    # Signal Performance Aggregation
    # ============================================================
    
    async def compute_signal_performance(self) -> bool:
        """
        Aggregate performance metrics per alert type
        
        Computes:
        - Total signals per type
        - Win rate
        - Average confidence
        - Total hypothetical P&L
        - Average time to resolution
        
        Returns True if successful
        """
        try:
            cursor = self.db_conn.cursor()
            
            # First check if signal_performance table exists
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'signal_performance'
                )
            """)
            
            if not cursor.fetchone()[0]:
                print("signal_performance table doesn't exist yet. Run migrations first.")
                cursor.close()
                return False
            
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
                    SUM(COALESCE(hypothetical_pnl_usd, 0)) as total_hypothetical_pnl,
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
            print(f"Error computing signal performance: {e}")
            return False
    
    # ============================================================
    # Wallet Profile Learning
    # ============================================================
    
    async def update_wallet_signal_accuracy(self) -> int:
        """
        Update wallet profiles with their signal accuracy
        
        For each wallet that has triggered alerts:
        1. Calculate their historical accuracy
        2. Update follow_priority based on performance
        
        Returns number of wallets updated
        """
        try:
            cursor = self.db_conn.cursor()
            
            # First ensure wallet_profiles has the required columns
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns 
                    WHERE table_name = 'wallet_profiles' 
                    AND column_name = 'signal_accuracy'
                )
            """)
            
            if not cursor.fetchone()[0]:
                print("wallet_profiles.signal_accuracy doesn't exist yet. Run migrations first.")
                cursor.close()
                return 0
            
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
                    HAVING COUNT(*) >= 3  -- Need at least 3 signals to compute accuracy
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
            
            updated = cursor.rowcount
            self.db_conn.commit()
            cursor.close()
            
            return updated
            
        except Exception as e:
            self.db_conn.rollback()
            print(f"Error updating wallet accuracy: {e}")
            return 0
    
    # ============================================================
    # Main Entry Point
    # ============================================================
    
    async def run_all_updates(self) -> dict:
        """
        Run all tracking updates in sequence
        
        Returns dict with counts of updates made
        """
        print(f"[{datetime.now()}] Starting resolution tracking...")
        
        results = {
            'markets_resolved': 0,
            'alerts_updated': 0,
            'signal_performance_computed': False,
            'wallets_updated': 0
        }
        
        # 1. Poll for market resolutions
        print("  Polling market resolutions...")
        results['markets_resolved'] = await self.poll_market_resolutions()
        print(f"    → {results['markets_resolved']} markets resolved")
        
        # 2. Update alert outcomes
        print("  Updating alert outcomes...")
        results['alerts_updated'] = await self.update_alert_outcomes()
        print(f"    → {results['alerts_updated']} alerts updated")
        
        # 3. Compute signal performance
        print("  Computing signal performance...")
        results['signal_performance_computed'] = await self.compute_signal_performance()
        print(f"    → {'Success' if results['signal_performance_computed'] else 'Failed'}")
        
        # 4. Update wallet accuracy
        print("  Updating wallet signal accuracy...")
        results['wallets_updated'] = await self.update_wallet_signal_accuracy()
        print(f"    → {results['wallets_updated']} wallets updated")
        
        print(f"[{datetime.now()}] Resolution tracking complete!")
        
        return results
    
    def get_performance_report(self) -> list:
        """
        Get a summary of signal performance for display
        
        Returns list of dicts with performance by alert type
        """
        try:
            cursor = self.db_conn.cursor()
            
            cursor.execute("""
                SELECT
                    alert_type,
                    total_signals,
                    profitable_signals,
                    win_rate,
                    avg_confidence_score,
                    total_hypothetical_pnl,
                    avg_hours_to_resolution,
                    computed_at
                FROM signal_performance
                ORDER BY total_hypothetical_pnl DESC
            """)
            
            columns = ['alert_type', 'total_signals', 'profitable_signals', 
                      'win_rate', 'avg_confidence', 'total_pnl', 
                      'avg_hours_to_resolution', 'computed_at']
            
            results = []
            for row in cursor.fetchall():
                results.append(dict(zip(columns, row)))
            
            cursor.close()
            return results
            
        except Exception as e:
            print(f"Error getting performance report: {e}")
            return []


# ============================================================
# CLI Entry Point
# ============================================================

async def main():
    """Run resolution tracker from command line"""
    tracker = ResolutionTracker()
    
    try:
        results = await tracker.run_all_updates()
        
        # Print performance report
        print("\n" + "="*60)
        print("SIGNAL PERFORMANCE REPORT (Last 30 Days)")
        print("="*60)
        
        report = tracker.get_performance_report()
        
        if report:
            print(f"\n{'Alert Type':<25} {'Signals':>8} {'Win Rate':>10} {'Total P&L':>12}")
            print("-"*60)
            
            for row in report:
                win_rate_pct = (row['win_rate'] or 0) * 100
                total_pnl = row['total_pnl'] or 0
                pnl_color = "+" if total_pnl >= 0 else ""
                
                print(f"{row['alert_type']:<25} {row['total_signals']:>8} {win_rate_pct:>9.1f}% {pnl_color}${total_pnl:>10,.0f}")
        else:
            print("\nNo performance data yet. Run ARGUS live to generate alerts,")
            print("then wait for markets to resolve to see performance metrics.")
        
        print("\n")
        
    finally:
        tracker.close()


if __name__ == "__main__":
    asyncio.run(main())
