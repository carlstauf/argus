#!/usr/bin/env python3
"""
ARGUS - Main Entry Point
The All-Seeing Intelligence Layer for Prediction Markets

Usage:
    python argus.py init          # Initialize database
    python argus.py live          # Launch LIVE intelligence terminal
    python argus.py ingest        # Run data ingestion (background)
    python argus.py dashboard     # Launch dashboard
    python argus.py query <name>  # Run intelligence query
"""

import sys
import os
import time
import asyncio
import psycopg2
from pathlib import Path
from datetime import datetime
from collections import deque
from typing import List, Dict, Tuple

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from dotenv import load_dotenv
load_dotenv()

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich.text import Text
from rich.markup import escape
from rich.style import Style
from rich import box


def print_banner():
    """Print the ARGUS banner"""
    banner = """
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║     █████╗ ██████╗  ██████╗ ██╗   ██╗███████╗           ║
    ║    ██╔══██╗██╔══██╗██╔════╝ ██║   ██║██╔════╝           ║
    ║    ███████║██████╔╝██║  ███╗██║   ██║███████╗           ║
    ║    ██╔══██║██╔══██╗██║   ██║██║   ██║╚════██║           ║
    ║    ██║  ██║██║  ██║╚██████╔╝╚██████╔╝███████║           ║
    ║    ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝  ╚═════╝ ╚══════╝           ║
    ║                                                           ║
    ║         The All-Seeing Intelligence Layer  👁️             ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
    """
    print(banner)


def cmd_init():
    """Initialize the database schema"""
    print("\n[ARGUS] Initializing database...\n")
    from src.db.init_schema import initialize_schema
    initialize_schema()


def cmd_ingest():
    """Run the data ingestion pipeline"""
    print("\n[ARGUS] Starting data ingestion...\n")
    from src.api.ingestor import ArgusIngestor

    ingestor = ArgusIngestor()

    # Initial load
    print("[INIT] Loading markets...")
    ingestor.ingest_markets()

    print("[INIT] Loading trades...")
    ingestor.ingest_trades(limit=500)

    # Start surveillance
    print("\n[INIT] Starting real-time surveillance...\n")
    ingestor.run_surveillance(interval_seconds=30)


def cmd_dashboard():
    """Launch the terminal dashboard"""
    print("\n[ARGUS] Launching dashboard...\n")
    from src.ui.dashboard import ArgusDashboard

    dashboard = ArgusDashboard()
    dashboard.run(refresh_seconds=5)


def cmd_query(query_name: str = None):
    """Run an intelligence query"""
    from rich.console import Console
    from rich.table import Table
    from src.db.queries import IntelligenceQueries

    console = Console()

    available_queries = {
        'fresh': ('Fresh Wallets with Large Bets', IntelligenceQueries.fresh_wallets_with_large_bets()),
        'insider': ('Insider Trading Pattern', IntelligenceQueries.insider_trading_pattern()),
        'copy': ('Copy Leaderboard', IntelligenceQueries.copy_leaderboard()),
        'whale': ('Whale Movements', IntelligenceQueries.whale_movements()),
        'anomaly': ('Anomalous Trades', IntelligenceQueries.anomalous_trades()),
        'gap': ('Reality Gap Opportunities', IntelligenceQueries.reality_gap_opportunities())
    }

    if not query_name or query_name not in available_queries:
        console.print("\n[bold red]Error:[/bold red] Please specify a valid query name\n")
        console.print("[bold cyan]Available queries:[/bold cyan]")
        for key, (name, _) in available_queries.items():
            console.print(f"  • {key:10} - {name}")
        console.print("\n[bold]Usage:[/bold] python argus.py query <name>\n")
        return

    # Run the query
    console.print(f"\n[bold cyan]Running query:[/bold cyan] {available_queries[query_name][0]}\n")

    try:
        conn = psycopg2.connect(os.getenv('DATABASE_URL'))
        cursor = conn.cursor()

        query_sql = available_queries[query_name][1]
        cursor.execute(query_sql)

        results = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]

        # Display results in a table with proper formatting
        table = Table(
            title=available_queries[query_name][0],
            show_lines=True,
            expand=True,
            box=box.DOUBLE_EDGE
        )

        # Add columns with proper widths
        for col in columns:
            if 'address' in col.lower():
                table.add_column(col, style="cyan", width=20)
            elif 'question' in col.lower():
                table.add_column(col, style="white", width=40)
            elif 'usd' in col.lower() or 'value' in col.lower():
                table.add_column(col, style="green", justify="right", width=12)
            else:
                table.add_column(col, style="cyan")

        for row in results:
            table.add_row(*[str(val) if val is not None else 'N/A' for val in row])

        console.print(table)
        console.print(f"\n[dim]Found {len(results)} result(s)[/dim]\n")

        cursor.close()
        conn.close()

    except Exception as e:
        console.print(f"\n[bold red]Error running query:[/bold red] {e}\n")


# ============================================================
# LIVE TERMINAL - The Bloomberg Experience
# ============================================================

class LiveTerminal:
    """
    The LIVE Intelligence Terminal
    Combines real-time ingestion with a live-updating dashboard
    """

    def __init__(self):
        self.console = Console()
        self.db_conn = self._connect_db()

        # Initialize Intelligence Engine
        from src.intelligence.engine import IntelligenceEngine
        self.intelligence = IntelligenceEngine(self.db_conn)

        # Trade log (last 50 trades) - now with full data for links
        self.trade_log = deque(maxlen=50)

        # Stats
        self.total_ingested = 0
        self.last_ingest_time = None
        self.alerts_generated = 0
        self.total_volume_24h = 0.0

        # Seen trades cache
        self.seen_trades = set()

        # Thresholds
        self.fresh_wallet_hours = int(os.getenv('FRESH_WALLET_HOURS', 24))
        self.whale_threshold_usd = float(os.getenv('WHALE_THRESHOLD_USD', 5000))

    # ============================================================
    # URL Helpers
    # ============================================================

    @staticmethod
    def polymarket_market_url(condition_id: str, slug: str = None) -> str:
        """Generate Polymarket market URL - prefers slug, falls back to condition_id"""
        if slug:
            # Use slug if available (cleaner URL)
            return f"https://polymarket.com/event/{slug}"
        else:
            # Fall back to condition_id
            return f"https://polymarket.com/market/{condition_id}"

    @staticmethod
    def polymarket_profile_url(address: str) -> str:
        """Generate Polymarket profile URL for wallet address"""
        return f"https://polymarket.com/profile/{address}"

    @staticmethod
    def polymarket_tx_url(tx_hash: str) -> str:
        """Generate Polymarket transaction URL (if available)"""
        # Polymarket doesn't have direct TX links, but we can use profile
        # For now, return empty or use a generic link
        return f"https://polymarket.com"

    def make_clickable_link(self, text: str, url: str, style: str = "cyan") -> Text:
        """Create a clickable link in Rich Text"""
        link_text = Text()
        link_text.append(text, style=style)
        # Rich supports links in terminals that support OSC 8
        # Format: \x1b]8;;URL\x1b\\text\x1b]8;;\x1b\\
        # But Rich handles this automatically if we use the link method
        return link_text

    def _connect_db(self):
        """Establish database connection"""
        database_url = os.getenv('DATABASE_URL')
        return psycopg2.connect(database_url)

    def close(self):
        """Clean up"""
        if self.db_conn:
            self.db_conn.close()

    # ============================================================
    # Real-Time Ingestion (Every 2 seconds)
    # ============================================================

    async def ingest_live_data(self) -> List[Dict]:
        """
        Fetch and ingest new trades from Polymarket
        Returns list of new trades for the live ticker
        Only processes trades from the last 5 minutes to ensure freshness
        """
        from src.api.polymarket_client import PolymarketClient
        import time

        client = PolymarketClient()
        
        # Verify API health before fetching
        if not client.check_gamma_api_health():
            # API might be down, skip this cycle
            return []
        
        trades = client.get_trades(limit=50)

        if not trades:
            return []

        # Sort trades by timestamp descending (newest first)
        trades.sort(key=lambda x: x.get('timestamp', 0), reverse=True)

        # Filter to only very recent trades (last 5 minutes)
        current_time = time.time()
        recent_threshold = current_time - 300  # 5 minutes ago

        new_trades = []
        cursor = self.db_conn.cursor()

        for trade in trades:
            # Check if trade is recent enough
            trade_timestamp = trade.get('timestamp', 0)
            if trade_timestamp < recent_threshold:
                # Skip old trades - we only want recent data
                continue
            tx_hash = trade.get('transactionHash')

            # Skip if already seen
            if not tx_hash or tx_hash in self.seen_trades:
                continue

            wallet_address = trade.get('proxyWallet')
            condition_id = trade.get('conditionId')

            # Validate required fields
            if not wallet_address or not condition_id:
                continue
            
            # Validate wallet address format
            if not wallet_address.startswith('0x') or len(wallet_address) != 42:
                continue
            
            # Validate condition_id format
            if not condition_id.startswith('0x') or len(condition_id) < 20:
                continue

            try:
                # Calculate trade timestamp FIRST (before wallet operations)
                timestamp = trade.get('timestamp', int(time.time()))
                executed_at = datetime.fromtimestamp(timestamp)
                
                # Get the wallet's ACTUAL first trade timestamp from existing trades
                # This ensures freshness_score is based on real wallet age, not when we started tracking
                cursor.execute("""
                    SELECT MIN(executed_at) 
                    FROM trades 
                    WHERE wallet_address = %s
                """, (wallet_address,))
                
                result = cursor.fetchone()
                earliest_trade = result[0] if result and result[0] else None
                
                # Use the earliest trade timestamp we have, or this trade's timestamp if it's the first
                if earliest_trade:
                    # Wallet already has trades - use the earliest one
                    actual_first_seen = earliest_trade
                else:
                    # This is the first trade from this wallet - use this trade's timestamp
                    actual_first_seen = executed_at
                
                # Ensure wallet exists (upsert) - use ACTUAL first trade date, not NOW()
                # This is critical: first_seen_at should be when wallet FIRST traded, not when we first saw it
                cursor.execute("""
                    INSERT INTO wallets (address, first_seen_at, last_active_at)
                    VALUES (%s, %s, NOW())
                    ON CONFLICT (address) DO UPDATE SET
                        last_active_at = NOW(),
                        -- Keep the EARLIEST first_seen_at (don't let it get newer)
                        first_seen_at = LEAST(wallets.first_seen_at, EXCLUDED.first_seen_at)
                """, (wallet_address, actual_first_seen))

                # Ensure market exists (upsert) - include slug if available
                slug = trade.get('slug') or trade.get('eventSlug')
                cursor.execute("""
                    INSERT INTO markets (condition_id, question, slug, status)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (condition_id) DO UPDATE SET
                        slug = COALESCE(markets.slug, EXCLUDED.slug)
                """, (condition_id, trade.get('title', 'Unknown Market'), slug, 'ACTIVE'))

                # Trade timestamp already calculated above

                # Validate and calculate trade values
                size = float(trade.get('size', 0))
                price = float(trade.get('price', 0))
                
                # Skip invalid trades
                if size <= 0 or price <= 0 or price > 1:
                    continue
                
                value_usd = size * price
                
                # Skip trades with invalid USD values
                if value_usd <= 0 or value_usd > 10000000:  # Sanity check: max $10M
                    continue

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
                    wallet_address,
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
                    # New trade!
                    self.seen_trades.add(tx_hash)
                    self.total_ingested += 1

                    # Update wallet stats
                    cursor.execute("""
                        UPDATE wallets SET
                            total_trades = total_trades + 1,
                            total_volume_usd = total_volume_usd + %s
                        WHERE address = %s
                    """, (value_usd, wallet_address))

                    # Commit before running intelligence analysis
                    self.db_conn.commit()

                    # Run Intelligence Engine analysis
                    is_alert = await self._run_intelligence_analysis(
                        wallet_address, condition_id, value_usd, timestamp, cursor
                    )

                    # Get market slug from trade data (API already provides it!)
                    slug = trade.get('slug') or trade.get('eventSlug')
                    
                    # Validate slug format (should be alphanumeric with hyphens)
                    if slug and not isinstance(slug, str):
                        slug = None
                    elif slug and len(slug) > 200:  # Sanity check
                        slug = None

                    # Update market with slug if we have it
                    if slug:
                        try:
                            cursor.execute("""
                                UPDATE markets SET slug = %s
                                WHERE condition_id = %s AND (slug IS NULL OR slug = '')
                            """, (slug, condition_id))
                        except Exception:
                            # Skip if slug update fails
                            pass

                    # Add to ticker log with full data for links
                    new_trades.append({
                        'time': executed_at,
                        'wallet': wallet_address[:10] + '...',
                        'wallet_full': wallet_address,
                        'side': trade.get('side', 'BUY'),
                        'outcome': trade.get('outcome', 'Yes'),
                        'value_usd': value_usd,
                        'title': trade.get('title', 'Unknown')[:40],
                        'condition_id': condition_id,
                        'tx_hash': tx_hash,
                        'is_alert': is_alert,
                        'slug': slug  # Use slug from API directly!
                    })

                    # Update 24h volume
                    self.total_volume_24h += value_usd

            except Exception as e:
                # Rollback transaction on error
                self.db_conn.rollback()
                # Silent fail to keep UI clean
                pass

        self.db_conn.commit()
        cursor.close()

        self.last_ingest_time = datetime.now()
        return new_trades

    async def _run_intelligence_analysis(
        self, wallet_address: str, condition_id: str, value_usd: float, timestamp: int, cursor
    ) -> bool:
        """
        Run Intelligence Engine analysis on a trade
        Returns True if any alert was triggered
        """

        # Prepare trade dict for analysis
        trade_data = {
            'wallet_address': wallet_address,
            'condition_id': condition_id,
            'value_usd': value_usd,
            'timestamp': timestamp
        }

        try:
            # Run all detection algorithms
            alerts = await self.intelligence.analyze(trade_data)

            # Save alerts to database
            alert_triggered = False
            for alert in alerts:
                if self.intelligence.save_alert(alert):
                    self.alerts_generated += 1
                    alert_triggered = True

            return alert_triggered

        except Exception as e:
            # Silent fail
            return False

    # ============================================================
    # Data Fetchers for Dashboard
    # ============================================================

    def get_suspicious_wallets(self, limit: int = 15) -> List[Tuple]:
        """
        Get TRUE INSIDER candidates - ULTRA STRICT
        
        REAL INSIDER CRITERIA:
        - EXACTLY 1-2 trades total (not a day trader)
        - Single trade >= $10,000 (serious conviction)
        - Fresh wallet (< 48h old)
        - NOT sports betting (vs., o/u, spread)
        - NOT crypto gambling (up or down, price above/below)
        
        This is it. No exceptions. One big conviction bet = insider.
        """
        from src.api.polymarket_client import PolymarketClient
        
        cursor = self.db_conn.cursor()

        # ULTRA STRICT: Only wallets with 1-2 trades, one being $10k+
        cursor.execute("""
            WITH recent_trades AS (
                SELECT 
                    t.wallet_address,
                    t.value_usd,
                    t.side,
                    t.condition_id,
                    t.executed_at,
                    m.question
                FROM trades t
                LEFT JOIN markets m ON t.condition_id = m.condition_id
                WHERE t.executed_at >= NOW() - INTERVAL '48 hours'
            ),
            wallet_activity AS (
                SELECT 
                    wallet_address,
                    COUNT(*) as trade_count,
                    MAX(value_usd) as biggest_trade,
                    SUM(value_usd) as total_volume,
                    MIN(executed_at) as first_trade,
                    -- Get the question of the biggest trade
                    (ARRAY_AGG(question ORDER BY value_usd DESC))[1] as biggest_market_question,
                    -- Check if ANY trade is on gambling markets
                    BOOL_OR(
                        LOWER(question) LIKE '%%vs.%%' OR
                        LOWER(question) LIKE '%%vs %%' OR
                        LOWER(question) LIKE '%%o/u%%' OR
                        LOWER(question) LIKE '%%spread%%' OR
                        LOWER(question) LIKE '%%over/under%%' OR
                        LOWER(question) LIKE '%%up or down%%' OR
                        LOWER(question) LIKE '%%bitcoin%%' OR
                        LOWER(question) LIKE '%%btc%%' OR
                        LOWER(question) LIKE '%%ethereum%%' OR
                        LOWER(question) LIKE '%%solana%%' OR
                        LOWER(question) LIKE '%%xrp%%' OR
                        LOWER(question) LIKE '%%price above%%' OR
                        LOWER(question) LIKE '%%price below%%'
                    ) as is_gambler
                FROM recent_trades
                GROUP BY wallet_address
            )
            SELECT 
                wa.wallet_address,
                EXTRACT(EPOCH FROM (NOW() - wa.first_trade)) / 3600 as age_hours,
                wa.trade_count,
                wa.total_volume,
                100 as freshness_score,
                wa.biggest_market_question,    -- Returning Question instead of P&L
                0 as win_rate
            FROM wallet_activity wa
            WHERE 
                -- EXACTLY 1-2 trades (not a day trader)
                wa.trade_count <= 2
                -- BIG SINGLE BET: At least $10k on one trade
                AND wa.biggest_trade >= 10000
                -- NOT gambling on sports/crypto
                AND wa.is_gambler = FALSE
            ORDER BY wa.biggest_trade DESC
            LIMIT %s
        """, (limit,))

        candidates = cursor.fetchall()
        cursor.close()
        
        # Verify via API that these are truly fresh wallets
        client = PolymarketClient()
        verified_wallets = []
        
        for wallet_data in candidates:
            address = wallet_data[0]
            
            try:
                is_fresh, api_age = client.is_wallet_truly_fresh(address, max_age_hours=72)
                if is_fresh:
                    verified_wallets.append(wallet_data)
            except Exception:
                # If API fails, include with DB data
                verified_wallets.append(wallet_data)
            
            if len(verified_wallets) >= limit:
                break
        
        return verified_wallets

    def get_recent_alerts(self, limit: int = 15) -> List[Tuple]:
        """Get recent CRITICAL and HIGH alerts"""
        cursor = self.db_conn.cursor()

        cursor.execute("""
            SELECT
                a.alert_type,
                a.severity,
                a.title,
                a.created_at,
                a.confidence_score,
                a.wallet_address,
                a.condition_id,
                m.slug
            FROM alerts a
            LEFT JOIN markets m ON a.condition_id = m.condition_id
            WHERE a.severity IN ('CRITICAL', 'HIGH', 'MEDIUM')
            ORDER BY a.created_at DESC
            LIMIT %s
        """, (limit,))

        results = cursor.fetchall()
        cursor.close()
        return results

    def get_stats(self) -> Dict:
        """Get system stats"""
        cursor = self.db_conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM wallets")
        total_wallets = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM trades")
        total_trades = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM markets WHERE status = 'ACTIVE'")
        active_markets = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM alerts WHERE is_read = FALSE")
        unread_alerts = cursor.fetchone()[0]

        # 24h volume
        cursor.execute("""
            SELECT COALESCE(SUM(value_usd), 0)
            FROM trades
            WHERE executed_at > NOW() - INTERVAL '24 hours'
        """)
        volume_24h = float(cursor.fetchone()[0] or 0)

        # Recent trades (last hour)
        cursor.execute("""
            SELECT COUNT(*)
            FROM trades
            WHERE executed_at > NOW() - INTERVAL '1 hour'
        """)
        trades_1h = cursor.fetchone()[0]

        cursor.close()

        return {
            'total_wallets': total_wallets,
            'total_trades': total_trades,
            'active_markets': active_markets,
            'unread_alerts': unread_alerts,
            'volume_24h': volume_24h,
            'trades_1h': trades_1h
        }

    # ============================================================
    # UI Rendering
    # ============================================================

    def make_header(self) -> Panel:
        """Create clean minimal header"""
        text = Text()
        text.append("A R G U S", style="bold bright_white")
        text.append("  ", style="dim")
        text.append("◉", style="bold magenta")
        text.append("  ", style="dim")
        text.append("Insider Intelligence", style="italic dim")

        # Minimal status
        status_text = Text()
        
        if self.last_ingest_time:
            seconds_ago = (datetime.now() - self.last_ingest_time).seconds
            if seconds_ago < 10:
                status_text.append("● LIVE", style="bold green")
            else:
                status_text.append("○ SYNC", style="yellow")
        else:
            status_text.append("○ INIT", style="dim")
        
        status_text.append("  ", style="dim")
        status_text.append(f"{datetime.now().strftime('%H:%M:%S')}", style="dim")

        subtitle = str(status_text)

        return Panel(
            text,
            style="dim",
            subtitle=subtitle,
            box=box.ROUNDED
        )

    def make_stats_panel(self, stats: Dict) -> Panel:
        """Create enhanced stats panel"""
        content = Text()
        content.append("📊 MARKET STATS\n", style="bold cyan")
        content.append(f"Active Markets: ", style="dim")
        content.append(f"{stats['active_markets']:,}\n", style="cyan bold")
        
        content.append(f"24h Volume: ", style="dim")
        content.append(f"${stats['volume_24h']:,.0f}\n", style="green bold")
        
        content.append(f"Trades (1h): ", style="dim")
        content.append(f"{stats['trades_1h']:,}\n", style="cyan")
        
        content.append("\n👥 TRACKING\n", style="bold cyan")
        content.append(f"Wallets: ", style="dim")
        content.append(f"{stats['total_wallets']:,}\n", style="cyan")
        content.append(f"Total Trades: ", style="dim")
        content.append(f"{stats['total_trades']:,}\n", style="cyan")
        
        content.append("\n⚡ SESSION\n", style="bold cyan")
        content.append(f"Ingested: ", style="dim")
        content.append(f"{self.total_ingested:,}\n", style="green bold")
        
        content.append("\n🚨 ALERTS\n", style="bold yellow")
        alert_style = "yellow bold" if stats['unread_alerts'] > 0 else "dim"
        content.append(f"Unread: ", style="dim")
        content.append(f"{stats['unread_alerts']:,}", style=alert_style)

        return Panel(
            content,
            title="[dim]STATS[/dim]",
            border_style="dim",
            box=box.ROUNDED
        )

    def make_ticker(self) -> Panel:
        """Create enhanced live trade ticker with clickable links"""
        table = Table(
            show_header=True,
            header_style="bold cyan",
            box=box.SIMPLE,
            expand=True,
            show_lines=False
        )

        table.add_column("Time", width=8, style="dim")
        table.add_column("Wallet", width=18, style="cyan")
        table.add_column("Side", width=6)
        table.add_column("Value", width=12, justify="right")
        table.add_column("Market", style="white", ratio=2)

        # Show last 20 trades
        for trade in list(self.trade_log)[-20:]:
            time_str = trade['time'].strftime('%H:%M:%S')

            # Color by side
            side_style = "bold green" if trade['side'] == 'BUY' else "bold red"
            side_text = Text(trade['side'], style=side_style)

            # Wallet (not clickable - only market is clickable)
            wallet_text = Text()
            wallet_short = trade['wallet']
            wallet_text.append(wallet_short, style="cyan")

            # Value with color coding
            value_text = Text()
            value = trade['value_usd']
            if value >= 10000:
                value_style = "bold bright_green"
            elif value >= 1000:
                value_style = "green"
            else:
                value_style = "white"
            value_text.append(f"${value:,.0f}", style=value_style)

            # Market with clickable Polymarket link (PRIMARY CLICK TARGET)
            market_text = Text()
            if trade.get('is_alert'):
                market_text.append("🚨 ", style="bold red")
            if trade.get('condition_id'):
                market_url = self.polymarket_market_url(trade['condition_id'], trade.get('slug'))
                # Make market link very prominent - green, bold, underlined
                link_style = Style(link=market_url, color="bright_green", bold=True, underline=True)
                market_text.append(trade['title'][:45], style=link_style)
            else:
                market_text.append(trade['title'][:45], style="white")

            # Row style for alerts
            row_style = "bold red" if trade.get('is_alert') else None

            table.add_row(
                time_str,
                wallet_text,
                side_text,
                value_text,
                market_text,
                style=row_style
            )

        # Add footer with link instructions and data freshness
        footer = Text()
        footer.append("\n💡 ", style="dim")
        footer.append("Click ", style="dim italic")
        footer.append("GREEN MARKET NAMES", style="bold bright_green italic")
        footer.append(" → Opens Polymarket", style="dim italic")
        footer.append("\n📊 ", style="dim")
        footer.append("Data: Last 5 minutes only", style="dim italic")
        footer.append(" • ", style="dim")
        footer.append("Sorted: Newest first", style="dim italic")

        return Panel(
            table,
            title="[bold white]FEED[/bold white]",
            subtitle=f"{len(self.trade_log)} trades",
            border_style="dim",
            box=box.ROUNDED
        )

    def make_panopticon(self, wallets: List[Tuple]) -> Panel:
        """Create enhanced fresh wallet monitor"""
        table = Table(
            show_header=True,
            header_style="bold magenta",
            box=box.SIMPLE,
            expand=True,
            show_lines=False
        )

        table.add_column("Address", style="dim cyan", no_wrap=True, width=14)
        table.add_column("Age", justify="right", style="yellow", width=4)
        table.add_column("Bet", justify="right", style="bold green", width=8)
        table.add_column("Target Market", style="white", ratio=1, no_wrap=True)

        for wallet in wallets:
            # Tuple: (addr, age, trades, vol, fresh, question, win_rate)
            address = wallet[0]
            age_hours = wallet[1]
            volume_usd = wallet[3]
            question = wallet[5] if len(wallet) > 5 else "Unknown"

            # Format address
            address_disp = f"{address[:6]}...{address[-4:]}"
            
            # Format age
            if age_hours < 1:
                age_str = "<1h"
            else:
                age_str = f"{age_hours:.1f}h"

            table.add_row(
                address_disp,
                age_str,
                f"${volume_usd:,.0f}",
                question
            )

        if not wallets:
            # Better empty state
            empty_text = Text()
            empty_text.append("\n  ✓ ", style="green")
            empty_text.append("No insider candidates detected\n", style="dim")
            empty_text.append("    Criteria: $5k+ single trade, ≤2 trades, No crypto/sports\n", style="dim italic")
            table.add_row(empty_text, "", "", "")

        return Panel(
            table,
            title="[bold magenta]🎯 INSIDER CANDIDATES[/bold magenta]",
            subtitle="Big Bets | Fresh Wallets | Non-Gambling",
            border_style="magenta",
            box=box.ROUNDED
        )

    def make_alerts_panel(self, alerts: List[Tuple]) -> Panel:
        """Create enhanced alerts panel with links"""
        table = Table(
            show_header=True,
            header_style="bold yellow",
            box=box.SIMPLE,
            expand=True,
            show_lines=False
        )

        table.add_column("", width=3)
        table.add_column("Alert", style="white", ratio=2)
        table.add_column("Conf", width=6, justify="right")
        table.add_column("Links", width=8)

        # Alert type icons
        alert_icons = {
            'CRITICAL_FRESH': '🔴',
            'SUSPICIOUS_STRUCTURING': '🔨',
            'WHALE_ANOMALY': '📊',
            'WHALE_MOVE': '🐋',
            'FRESH_WALLET': '🔴',
            'INSIDER_PATTERN': '💎',
            'ANOMALY': '⚡'
        }

        for alert in alerts:
            alert_type, severity, title, created_at, confidence, wallet, condition_id, slug = alert[:8]

            # Get icon
            icon = alert_icons.get(alert_type, '⚠️')

            # Color by severity
            if severity == 'CRITICAL':
                sev_style = "bold red"
            elif severity == 'HIGH':
                sev_style = "bold yellow"
            else:
                sev_style = "bold blue"

            # Title with truncation
            title_text = Text()
            title_text.append(title[:50], style="white")
            if len(title) > 50:
                title_text.append("...", style="dim")

            # Confidence with color
            conf_text = Text()
            conf_pct = int(confidence * 100) if confidence else 0
            if conf_pct >= 80:
                conf_style = "bold green"
            elif conf_pct >= 60:
                conf_style = "yellow"
            else:
                conf_style = "dim"
            conf_text.append(f"{conf_pct}%", style=conf_style)

            # Links column with clickable links
            links_text = Text()
            if wallet:
                wallet_url = self.polymarket_profile_url(wallet)
                link_style = Style(link=wallet_url, color="cyan", underline=True)
                links_text.append("👤", style=link_style)
            if condition_id:
                market_url = self.polymarket_market_url(condition_id, slug)
                link_style = Style(link=market_url, color="green", underline=True)
                links_text.append(" 📊", style=link_style)
            if not wallet and not condition_id:
                links_text.append("--", style="dim")

            table.add_row(
                icon,
                title_text,
                conf_text,
                links_text,
                style=sev_style
            )

        if not alerts:
            table.add_row("", "No alerts detected", "", "", style="dim")

        footer = Text()
        footer.append("💡 ", style="dim")
        footer.append("👤 = Wallet | ", style="dim")
        footer.append("📊 = Market", style="dim")

        return Panel(
            table,
            title="[bold yellow]SIGNALS[/bold yellow]",
            subtitle=f"{len(alerts)} alerts",
            border_style="yellow",
            box=box.ROUNDED
        )

    def make_layout(self) -> Layout:
        """Create the main layout"""
        layout = Layout()

        # Split into header and body
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body")
        )

        # Split body into left (Insiders) and right (Feed/Alerts)
        layout["body"].split_row(
            Layout(name="left", ratio=4),
            Layout(name="right", ratio=6)
        )

        # Left column: JUST Insider Candidates (Panopticon)
        layout["left"].update(self.make_panopticon(self.get_suspicious_wallets(20)))

        # Right column: Split into Feed, Signals, Stats
        layout["right"].split_column(
            Layout(name="ticker", ratio=4),
            Layout(name="alerts", ratio=3),
            Layout(name="stats", size=9),
            Layout(name="footer", size=3)
        )

        # Update panels
        layout["header"].update(self.make_header())

        stats = self.get_stats()
        alerts = self.get_recent_alerts(10)

        layout["ticker"].update(self.make_ticker())
        layout["alerts"].update(self.make_alerts_panel(alerts))
        layout["stats"].update(self.make_stats_panel(stats))
        layout["footer"].update(self.make_footer())

        return layout

    def make_footer(self) -> Panel:
        """Create footer with clickable URL links"""
        content = Text()
        content.append("🔗 QUICK LINKS", style="bold cyan")
        content.append(" (Latest Trade)\n", style="dim")
        
        # Show URLs for most recent trade if available
        if self.trade_log:
            latest = list(self.trade_log)[-1]
            
            if latest.get('condition_id'):
                market_url = self.polymarket_market_url(latest['condition_id'], latest.get('slug'))
                content.append("Market: ", style="dim")
                link_style = Style(link=market_url, color="green", underline=True)
                content.append("Click here", style=link_style)
                content.append(f" ({market_url})", style="dim")
                content.append("\n", style="dim")
            
            if latest.get('wallet_full'):
                wallet_url = self.polymarket_profile_url(latest['wallet_full'])
                content.append("Profile: ", style="dim")
                link_style = Style(link=wallet_url, color="cyan", underline=True)
                content.append("Click here", style=link_style)
                content.append(f" ({wallet_url})", style="dim")
        else:
            content.append("No trades yet...", style="dim")
        
        content.append("\n\n💡 ", style="dim")
        content.append("Click underlined text to open", style="dim italic")
        content.append("\n", style="dim")
        content.append("   Full URLs shown for copying", style="dim italic")

        return Panel(
            content,
            title="[bold dim]🔗 LINKS[/bold dim]",
            border_style="dim",
            box=box.SIMPLE
        )

    def print_urls_for_trade(self, trade: Dict):
        """Print URLs for a trade (helper for debugging/access)"""
        if trade.get('condition_id'):
            market_url = self.polymarket_market_url(trade['condition_id'], trade.get('slug'))
            self.console.print(f"\n[green]Market:[/green] {market_url}")
        if trade.get('wallet_full'):
            self.console.print(f"[cyan]Profile:[/cyan] {self.polymarket_profile_url(trade['wallet_full'])}")

    # ============================================================
    # Main Live Loop
    # ============================================================

    async def run_live(self):
        """Run the live terminal"""

        self.console.print("\n[bold cyan]Starting LIVE Intelligence Terminal...[/bold cyan]\n")
        self.console.print("[dim]Ingesting data every 2 seconds...[/dim]")
        self.console.print("[dim]Dashboard refreshes every 5 seconds...[/dim]")
        self.console.print("[dim]Press Ctrl+C to exit[/dim]\n")
        self.console.print("[bold yellow]💡 TIP:[/bold yellow] Links are clickable in supported terminals")
        self.console.print("[dim]   Compatible: iTerm2, Windows Terminal, GNOME Terminal, Alacritty[/dim]")
        self.console.print("[dim]   If links don't work, copy URLs from the footer panel[/dim]\n")

        time.sleep(2)

        # Initial data load
        self.console.print("[cyan]Loading initial data...[/cyan]")
        from src.api.ingestor import ArgusIngestor
        ingestor = ArgusIngestor()
        ingestor.ingest_markets()
        ingestor.ingest_trades(limit=100)
        ingestor.close()

        self.console.print("[green]✓ Ready![/green]\n")
        time.sleep(1)

        # Start live loop
        try:
            with Live(self.make_layout(), refresh_per_second=4, console=self.console) as live:
                last_dashboard_update = time.time()

                while True:
                    # Ingest new trades every 2 seconds
                    new_trades = await self.ingest_live_data()

                    # Add to ticker log
                    for trade in new_trades:
                        self.trade_log.append(trade)

                    # Update dashboard every 5 seconds
                    current_time = time.time()
                    if current_time - last_dashboard_update >= 5:
                        live.update(self.make_layout())
                        last_dashboard_update = current_time

                    await asyncio.sleep(2)

        except KeyboardInterrupt:
            self.console.print("\n\n[bold cyan]Shutting down ARGUS... 👁️[/bold cyan]\n")
            self.close()


def cmd_live():
    """Launch the LIVE terminal"""
    terminal = LiveTerminal()
    asyncio.run(terminal.run_live())


def cmd_help():
    """Show help message"""
    print("""
ARGUS - The All-Seeing Intelligence Layer

Commands:
    init          Initialize database schema
    live          🔴 Launch LIVE intelligence terminal (recommended)
    ingest        Run data ingestion and surveillance (background)
    dashboard     Launch static dashboard
    query <name>  Run intelligence query

Intelligence Queries:
    fresh         Fresh wallets with large bets (insider signals)
    insider       Insider trading patterns (trades before news)
    copy          Copy leaderboard (profitable traders to follow)
    whale         Whale movements (large position tracking)
    anomaly       Statistical anomalies (outlier trades)
    gap           Reality gap opportunities (news vs. market price)

Examples:
    python argus.py init              # First time setup
    python argus.py live              # Launch live terminal ⭐
    python argus.py query fresh       # Query fresh wallets

Configuration:
    Copy .env.example to .env and configure your settings.
    Ensure PostgreSQL is running and DATABASE_URL is set.

Documentation:
    See README.md for full documentation.
    """)


def main():
    """Main entry point"""
    print_banner()

    if len(sys.argv) < 2:
        cmd_help()
        return

    command = sys.argv[1].lower()

    commands = {
        'init': cmd_init,
        'live': cmd_live,
        'ingest': cmd_ingest,
        'dashboard': cmd_dashboard,
        'query': lambda: cmd_query(sys.argv[2] if len(sys.argv) > 2 else None),
        'help': cmd_help,
        '--help': cmd_help,
        '-h': cmd_help
    }

    if command in commands:
        commands[command]()
    else:
        print(f"\nUnknown command: {command}")
        cmd_help()


if __name__ == "__main__":
    main()
