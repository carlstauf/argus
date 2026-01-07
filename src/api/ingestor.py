"""
ARGUS - Data Ingestor
The PANOPTICON Engine: Real-time surveillance of Polymarket
"""

import os
import time
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime
from typing import Dict, List, Optional
from dotenv import load_dotenv

from .polymarket_client import PolymarketClient

load_dotenv()


class ArgusIngestor:
    """
    The core ingestion engine.
    Continuously pulls data from Polymarket and stores it in the database.
    """

    def __init__(self):
        self.client = PolymarketClient()
        self.db_conn = self._connect_db()
        self.seen_trades = set()  # Cache to avoid duplicate processing

        # Thresholds from config
        self.fresh_wallet_hours = int(os.getenv('FRESH_WALLET_HOURS', 24))
        self.whale_threshold_usd = float(os.getenv('WHALE_THRESHOLD_USD', 5000))
        self.anomaly_sigma = float(os.getenv('ANOMALY_SIGMA', 2.0))

    def _connect_db(self):
        """Establish database connection"""
        database_url = os.getenv('DATABASE_URL')
        return psycopg2.connect(database_url)

    def close(self):
        """Clean up connections"""
        if self.db_conn:
            self.db_conn.close()

    # ============================================================
    # Market Ingestion
    # ============================================================

    def ingest_markets(self, batch_size: int = 100) -> int:
        """
        Fetch and store all active markets
        Returns: Number of markets ingested
        """
        print("[INGESTOR] Fetching markets...")

        markets = self.client.get_all_active_markets()
        if not markets:
            print("[INGESTOR] No markets found")
            return 0

        print(f"[INGESTOR] Processing {len(markets)} markets...")

        cursor = self.db_conn.cursor()
        inserted = 0

        for market in markets:
            condition_id = market.get('conditionId')
            if not condition_id:
                continue

            try:
                cursor.execute("""
                    INSERT INTO markets (
                        condition_id, question, slug, category,
                        end_date, status, total_volume_usd, current_liquidity_usd,
                        icon_url, event_slug
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (condition_id) DO UPDATE SET
                        total_volume_usd = EXCLUDED.total_volume_usd,
                        current_liquidity_usd = EXCLUDED.current_liquidity_usd,
                        status = EXCLUDED.status,
                        updated_at = NOW()
                """, (
                    condition_id,
                    market.get('question'),
                    market.get('slug'),
                    market.get('category'),
                    market.get('endDate'),
                    'ACTIVE',
                    float(market.get('volume', 0)),
                    float(market.get('liquidity', 0)),
                    market.get('icon'),
                    market.get('eventSlug')
                ))
                inserted += 1

            except Exception as e:
                print(f"[INGESTOR] Error inserting market {condition_id}: {e}")
                continue

        self.db_conn.commit()
        cursor.close()

        print(f"[INGESTOR] ✓ Ingested {inserted} markets")
        return inserted

    # ============================================================
    # Trade Ingestion & Wallet Discovery
    # ============================================================

    def ingest_trades(self, limit: int = 100) -> int:
        """
        Fetch and store recent trades
        Also discovers and profiles new wallets
        Returns: Number of new trades ingested
        """
        print("[INGESTOR] Fetching trades...")

        trades = self.client.get_trades(limit=limit)
        if not trades:
            print("[INGESTOR] No trades found")
            return 0

        new_trades = 0
        cursor = self.db_conn.cursor()

        for trade in trades:
            tx_hash = trade.get('transactionHash')

            # Skip if we've already processed this trade
            if not tx_hash or tx_hash in self.seen_trades:
                continue

            # Extract trade data
            wallet_address = trade.get('proxyWallet')
            condition_id = trade.get('conditionId')

            if not wallet_address or not condition_id:
                continue

            # Insert trade (with ensure methods inside try block)
            try:
                # Calculate trade timestamp FIRST
                timestamp = trade.get('timestamp', int(time.time()))
                executed_at = datetime.fromtimestamp(timestamp)
                
                # Ensure wallet and market exist (pass trade timestamp for accurate first_seen_at)
                self._ensure_wallet_exists(wallet_address, cursor, executed_at)
                self._ensure_market_exists(condition_id, cursor)

                size = float(trade.get('size', 0))
                price = float(trade.get('price', 0))
                value_usd = size * price

                cursor.execute("""
                    INSERT INTO trades (
                        transaction_hash, asset_id, wallet_address, proxy_wallet,
                        condition_id, side, outcome, outcome_index,
                        size, price, value_usd, timestamp, executed_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (transaction_hash) DO NOTHING
                    RETURNING id
                """, (
                    tx_hash,
                    trade.get('asset'),
                    wallet_address,
                    wallet_address,  # proxyWallet
                    condition_id,
                    trade.get('side', 'BUY'),
                    trade.get('outcome', 'Yes'),
                    trade.get('outcomeIndex'),
                    size,
                    price,
                    value_usd,
                    timestamp,
                    executed_at
                ))

                result = cursor.fetchone()
                if result:
                    new_trades += 1
                    self.seen_trades.add(tx_hash)

                    # Update wallet stats
                    self._update_wallet_stats(wallet_address, value_usd, cursor)

                    # Check for anomalies
                    self._check_trade_anomalies(
                        wallet_address, condition_id, value_usd, executed_at, cursor
                    )

            except Exception as e:
                # Rollback on any error to reset transaction
                self.db_conn.rollback()
                # Silent continue (don't spam console)
                continue

        self.db_conn.commit()
        cursor.close()

        print(f"[INGESTOR] ✓ Ingested {new_trades} new trades")
        return new_trades

    # ============================================================
    # Wallet Management
    # ============================================================

    def _ensure_wallet_exists(self, wallet_address: str, cursor, trade_timestamp: datetime = None) -> None:
        """
        Create wallet record if it doesn't exist
        Uses trade_timestamp as first_seen_at to ensure accurate wallet age
        """
        if trade_timestamp is None:
            trade_timestamp = datetime.now()
        
        # Check for existing earliest trade
        cursor.execute("""
            SELECT MIN(executed_at) 
            FROM trades 
            WHERE wallet_address = %s
        """, (wallet_address,))
        
        result = cursor.fetchone()
        earliest_trade = result[0] if result and result[0] else trade_timestamp
        
        cursor.execute("""
            INSERT INTO wallets (address, first_seen_at, last_active_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (address) DO UPDATE SET
                last_active_at = NOW(),
                first_seen_at = LEAST(wallets.first_seen_at, EXCLUDED.first_seen_at)
        """, (wallet_address, earliest_trade))

    def _ensure_market_exists(self, condition_id: str, cursor) -> None:
        """Create market record if it doesn't exist"""
        cursor.execute("""
            INSERT INTO markets (condition_id, question, status)
            VALUES (%s, %s, %s)
            ON CONFLICT (condition_id) DO NOTHING
        """, (condition_id, 'Unknown Market', 'ACTIVE'))

    def _update_wallet_stats(self, wallet_address: str, trade_value: float, cursor) -> None:
        """Update wallet's aggregate statistics"""
        cursor.execute("""
            UPDATE wallets SET
                total_trades = total_trades + 1,
                total_volume_usd = total_volume_usd + %s,
                last_active_at = NOW()
            WHERE address = %s
        """, (trade_value, wallet_address))

    # ============================================================
    # Anomaly Detection (Real-time)
    # ============================================================

    def _check_trade_anomalies(
        self,
        wallet_address: str,
        condition_id: str,
        value_usd: float,
        executed_at: datetime,
        cursor
    ) -> None:
        """
        Real-time anomaly detection on incoming trades
        """

        # Get wallet age
        cursor.execute("""
            SELECT EXTRACT(EPOCH FROM (NOW() - first_seen_at)) / 3600 as age_hours
            FROM wallets
            WHERE address = %s
        """, (wallet_address,))

        result = cursor.fetchone()
        wallet_age_hours = result[0] if result else 999999

        # ALERT 1: Fresh Wallet + Large Bet = INSIDER SIGNAL
        if wallet_age_hours < self.fresh_wallet_hours and value_usd > self.whale_threshold_usd:
            self._create_alert(
                alert_type='FRESH_WALLET',
                severity='CRITICAL',
                wallet_address=wallet_address,
                condition_id=condition_id,
                title=f'Fresh Wallet Alert: ${value_usd:,.2f} bet from {wallet_age_hours:.1f}h old wallet',
                description=f'Wallet {wallet_address[:10]}... made a ${value_usd:,.2f} bet only {wallet_age_hours:.1f} hours after creation. High probability of insider knowledge.',
                confidence_score=0.85,
                supporting_data={
                    'wallet_age_hours': wallet_age_hours,
                    'trade_value_usd': value_usd,
                    'threshold_usd': self.whale_threshold_usd
                },
                cursor=cursor
            )

        # ALERT 2: Whale Movement
        elif value_usd > self.whale_threshold_usd:
            cursor.execute("""
                SELECT is_whale, total_pnl_usd, win_rate
                FROM wallets
                WHERE address = %s
            """, (wallet_address,))

            wallet_data = cursor.fetchone()
            if wallet_data:
                is_whale, total_pnl, win_rate = wallet_data

                if is_whale or (total_pnl and total_pnl > 50000):
                    self._create_alert(
                        alert_type='WHALE_MOVE',
                        severity='HIGH',
                        wallet_address=wallet_address,
                        condition_id=condition_id,
                        title=f'Whale Movement: ${value_usd:,.2f}',
                        description=f'Known whale {wallet_address[:10]}... placed ${value_usd:,.2f} bet. Lifetime PnL: ${total_pnl:,.2f}, Win Rate: {win_rate*100:.1f}%',
                        confidence_score=0.70,
                        supporting_data={
                            'trade_value_usd': value_usd,
                            'wallet_lifetime_pnl': float(total_pnl) if total_pnl else 0,
                            'wallet_win_rate': float(win_rate) if win_rate else 0
                        },
                        cursor=cursor
                    )

    def _create_alert(
        self,
        alert_type: str,
        severity: str,
        wallet_address: str,
        condition_id: str,
        title: str,
        description: str,
        confidence_score: float,
        supporting_data: Dict,
        cursor
    ) -> None:
        """Create an alert in the database"""
        try:
            cursor.execute("""
                INSERT INTO alerts (
                    alert_type, severity, wallet_address, condition_id,
                    title, description, confidence_score, supporting_data
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                alert_type, severity, wallet_address, condition_id,
                title, description, confidence_score,
                psycopg2.extras.Json(supporting_data)
            ))

            print(f"[ALERT] {severity}: {title}")

        except Exception as e:
            print(f"[INGESTOR] Error creating alert: {e}")

    # ============================================================
    # Main Surveillance Loop
    # ============================================================

    def run_surveillance(self, interval_seconds: int = 30):
        """
        Main surveillance loop
        Continuously monitors markets and trades
        """
        print("\n" + "=" * 60)
        print("ARGUS SURVEILLANCE SYSTEM - ONLINE")
        print("=" * 60 + "\n")

        iteration = 0

        try:
            while True:
                iteration += 1
                print(f"\n[CYCLE {iteration}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

                # Refresh markets every 10 cycles (~5 minutes)
                if iteration % 10 == 1:
                    self.ingest_markets()

                # Always ingest latest trades
                self.ingest_trades(limit=100)

                print(f"[CYCLE {iteration}] Sleeping for {interval_seconds}s...")
                time.sleep(interval_seconds)

        except KeyboardInterrupt:
            print("\n\n[ARGUS] Shutting down surveillance...")
            self.close()
            print("[ARGUS] Goodbye. 👁️")


if __name__ == "__main__":
    print("\nStarting ARGUS Ingestor...")

    ingestor = ArgusIngestor()

    # Initial data load
    print("\n[INIT] Loading initial market data...")
    ingestor.ingest_markets()

    print("\n[INIT] Loading initial trade data...")
    ingestor.ingest_trades(limit=500)

    # Start real-time surveillance
    print("\n[INIT] Starting real-time surveillance...\n")
    ingestor.run_surveillance(interval_seconds=30)
