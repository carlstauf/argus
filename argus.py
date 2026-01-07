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

        # Trade log (last 50 trades)
        self.trade_log = deque(maxlen=50)

        # Stats
        self.total_ingested = 0
        self.last_ingest_time = None
        self.alerts_generated = 0

        # Seen trades cache
        self.seen_trades = set()

        # Thresholds
        self.fresh_wallet_hours = int(os.getenv('FRESH_WALLET_HOURS', 24))
        self.whale_threshold_usd = float(os.getenv('WHALE_THRESHOLD_USD', 5000))

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

    def ingest_live_data(self) -> List[Dict]:
        """
        Fetch and ingest new trades from Polymarket
        Returns list of new trades for the live ticker
        """
        from src.api.polymarket_client import PolymarketClient

        client = PolymarketClient()
        trades = client.get_trades(limit=50)

        if not trades:
            return []

        new_trades = []
        cursor = self.db_conn.cursor()

        for trade in trades:
            tx_hash = trade.get('transactionHash')

            # Skip if already seen
            if not tx_hash or tx_hash in self.seen_trades:
                continue

            wallet_address = trade.get('proxyWallet')
            condition_id = trade.get('conditionId')

            if not wallet_address or not condition_id:
                continue

            try:
                # Ensure wallet exists (upsert)
                cursor.execute("""
                    INSERT INTO wallets (address, first_seen_at, last_active_at)
                    VALUES (%s, NOW(), NOW())
                    ON CONFLICT (address) DO UPDATE SET
                        last_active_at = NOW()
                """, (wallet_address,))

                # Ensure market exists (upsert)
                cursor.execute("""
                    INSERT INTO markets (condition_id, question, status)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (condition_id) DO NOTHING
                """, (condition_id, trade.get('title', 'Unknown Market'), 'ACTIVE'))

                # Insert trade (upsert)
                timestamp = trade.get('timestamp', int(time.time()))
                executed_at = datetime.fromtimestamp(timestamp)

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

                    # Check for alerts
                    is_alert = self._check_trade_alert(
                        wallet_address, condition_id, value_usd, cursor
                    )

                    # Add to ticker log
                    new_trades.append({
                        'time': executed_at,
                        'wallet': wallet_address[:10] + '...',
                        'side': trade.get('side', 'BUY'),
                        'outcome': trade.get('outcome', 'Yes'),
                        'value_usd': value_usd,
                        'title': trade.get('title', 'Unknown')[:40],
                        'is_alert': is_alert
                    })

            except Exception as e:
                # Rollback transaction on error
                self.db_conn.rollback()
                # Silent fail to keep UI clean
                pass

        self.db_conn.commit()
        cursor.close()

        self.last_ingest_time = datetime.now()
        return new_trades

    def _check_trade_alert(
        self, wallet_address: str, condition_id: str, value_usd: float, cursor
    ) -> bool:
        """Check if trade triggers an alert. Returns True if alert created."""

        # Get wallet age
        cursor.execute("""
            SELECT EXTRACT(EPOCH FROM (NOW() - first_seen_at)) / 3600 as age_hours
            FROM wallets WHERE address = %s
        """, (wallet_address,))

        result = cursor.fetchone()
        wallet_age_hours = result[0] if result else 999999

        # CRITICAL: Fresh wallet + large bet
        if wallet_age_hours < self.fresh_wallet_hours and value_usd > self.whale_threshold_usd:
            cursor.execute("""
                INSERT INTO alerts (
                    alert_type, severity, wallet_address, condition_id,
                    title, description, confidence_score, supporting_data
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                'FRESH_WALLET',
                'CRITICAL',
                wallet_address,
                condition_id,
                f'🚨 INSIDER SIGNAL: ${value_usd:,.0f} from {wallet_age_hours:.1f}h old wallet',
                f'Fresh wallet {wallet_address[:10]}... placed ${value_usd:,.0f} bet',
                0.85,
                psycopg2.extras.Json({
                    'wallet_age_hours': wallet_age_hours,
                    'trade_value_usd': value_usd
                })
            ))

            self.alerts_generated += 1
            return True

        return False

    # ============================================================
    # Data Fetchers for Dashboard
    # ============================================================

    def get_suspicious_wallets(self, limit: int = 15) -> List[Tuple]:
        """Get fresh wallets with high volume"""
        cursor = self.db_conn.cursor()

        cursor.execute("""
            SELECT
                w.address,
                EXTRACT(EPOCH FROM (NOW() - w.first_seen_at)) / 3600 as age_hours,
                w.total_trades,
                w.total_volume_usd,
                w.freshness_score
            FROM wallets w
            WHERE
                w.freshness_score >= 50
                AND w.total_volume_usd > 100
            ORDER BY w.freshness_score DESC, w.total_volume_usd DESC
            LIMIT %s
        """, (limit,))

        results = cursor.fetchall()
        cursor.close()
        return results

    def get_recent_alerts(self, limit: int = 10) -> List[Tuple]:
        """Get recent CRITICAL alerts"""
        cursor = self.db_conn.cursor()

        cursor.execute("""
            SELECT
                a.severity,
                a.title,
                a.created_at,
                a.confidence_score
            FROM alerts a
            WHERE a.severity IN ('CRITICAL', 'HIGH')
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

        cursor.close()

        return {
            'total_wallets': total_wallets,
            'total_trades': total_trades,
            'active_markets': active_markets,
            'unread_alerts': unread_alerts
        }

    # ============================================================
    # UI Rendering
    # ============================================================

    def make_header(self) -> Panel:
        """Create header panel"""
        text = Text()
        text.append("ARGUS ", style="bold cyan")
        text.append("👁️ ", style="bold white")
        text.append("Live Intelligence Terminal", style="italic white")

        subtitle = f"Live @ {datetime.now().strftime('%H:%M:%S')}"
        if self.last_ingest_time:
            seconds_ago = (datetime.now() - self.last_ingest_time).seconds
            subtitle += f" | Last update: {seconds_ago}s ago"

        return Panel(
            text,
            style="bold cyan",
            subtitle=subtitle,
            box=box.DOUBLE_EDGE
        )

    def make_stats_panel(self, stats: Dict) -> Panel:
        """Create stats panel"""
        content = Text()
        content.append(f"Markets: {stats['active_markets']:,}\n", style="cyan")
        content.append(f"Wallets: {stats['total_wallets']:,}\n", style="cyan")
        content.append(f"Trades: {stats['total_trades']:,}\n", style="cyan")
        content.append(f"Ingested: {self.total_ingested:,}\n", style="green")
        content.append(f"Alerts: {stats['unread_alerts']:,}", style="yellow bold" if stats['unread_alerts'] > 0 else "dim")

        return Panel(
            content,
            title="[bold cyan]Stats[/bold cyan]",
            border_style="cyan",
            box=box.ROUNDED
        )

    def make_ticker(self) -> Panel:
        """Create live trade ticker"""
        table = Table(
            show_header=True,
            header_style="bold cyan",
            box=box.SIMPLE,
            expand=True,
            show_lines=False
        )

        table.add_column("Time", width=8, style="dim")
        table.add_column("Wallet", width=15, style="cyan")
        table.add_column("Side", width=6)
        table.add_column("Out", width=5)
        table.add_column("Value", width=10, justify="right")
        table.add_column("Market", style="white")

        # Show last 15 trades
        for trade in list(self.trade_log)[-15:]:
            time_str = trade['time'].strftime('%H:%M:%S')

            # Color by side
            side_style = "bold green" if trade['side'] == 'BUY' else "bold red"

            # Alert indicator
            market_text = trade['title']
            if trade.get('is_alert'):
                market_text = f"🚨 {market_text}"

            table.add_row(
                time_str,
                trade['wallet'],
                trade['side'],
                trade['outcome'][:3],
                f"${trade['value_usd']:,.0f}",
                market_text,
                style=side_style if trade.get('is_alert') else None
            )

        return Panel(
            table,
            title="[bold green]📊 LIVE TICKER[/bold green]",
            border_style="green",
            box=box.DOUBLE_EDGE
        )

    def make_panopticon(self, wallets: List[Tuple]) -> Panel:
        """Create suspicious wallets table"""
        table = Table(
            show_header=True,
            header_style="bold red",
            box=box.SIMPLE,
            expand=True,
            show_lines=True
        )

        table.add_column("Address", width=20, style="cyan")
        table.add_column("Age", width=10, justify="right")
        table.add_column("Trades", width=8, justify="right")
        table.add_column("Volume", width=12, justify="right", style="green")
        table.add_column("Fresh", width=8, justify="right")

        for wallet in wallets:
            address, age_hours, trades, volume, freshness = wallet

            # Format age
            if age_hours < 1:
                age_str = f"{int(age_hours * 60)}m"
            elif age_hours < 24:
                age_str = f"{age_hours:.1f}h"
            else:
                age_str = f"{age_hours/24:.1f}d"

            # Color by freshness
            row_style = "bold red" if freshness >= 90 else ("yellow" if freshness >= 70 else None)

            table.add_row(
                address[:20],
                age_str,
                str(trades),
                f"${volume:,.0f}",
                str(freshness),
                style=row_style
            )

        if not wallets:
            table.add_row("No suspicious activity detected", "", "", "", "", style="dim")

        return Panel(
            table,
            title="[bold red]🔴 THE PANOPTICON (Fresh Wallets)[/bold red]",
            subtitle="Auto-refreshes every 5 seconds",
            border_style="red",
            box=box.DOUBLE_EDGE
        )

    def make_alerts_panel(self, alerts: List[Tuple]) -> Panel:
        """Create alerts panel"""
        table = Table(
            show_header=True,
            header_style="bold yellow",
            box=box.SIMPLE,
            expand=True
        )

        table.add_column("Sev", width=8)
        table.add_column("Alert", style="white")
        table.add_column("Conf", width=6, justify="right")

        for alert in alerts:
            severity, title, created_at, confidence = alert

            sev_style = "bold red" if severity == 'CRITICAL' else "bold yellow"

            table.add_row(
                severity,
                title[:60],
                f"{confidence*100:.0f}%",
                style=sev_style
            )

        if not alerts:
            table.add_row("", "No critical alerts", "", style="dim")

        return Panel(
            table,
            title="[bold yellow]🚨 RECENT ALERTS[/bold yellow]",
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

        # Split body into left and right
        layout["body"].split_row(
            Layout(name="left", ratio=7),
            Layout(name="right", ratio=3)
        )

        # Split left into ticker and panopticon
        layout["left"].split_column(
            Layout(name="ticker", ratio=3),
            Layout(name="panopticon", ratio=2)
        )

        # Split right into stats and alerts
        layout["right"].split_column(
            Layout(name="stats", size=9),
            Layout(name="alerts")
        )

        # Update panels
        layout["header"].update(self.make_header())

        stats = self.get_stats()
        wallets = self.get_suspicious_wallets(15)
        alerts = self.get_recent_alerts(10)

        layout["stats"].update(self.make_stats_panel(stats))
        layout["ticker"].update(self.make_ticker())
        layout["panopticon"].update(self.make_panopticon(wallets))
        layout["alerts"].update(self.make_alerts_panel(alerts))

        return layout

    # ============================================================
    # Main Live Loop
    # ============================================================

    async def run_live(self):
        """Run the live terminal"""

        self.console.print("\n[bold cyan]Starting LIVE Intelligence Terminal...[/bold cyan]\n")
        self.console.print("[dim]Ingesting data every 2 seconds...[/dim]")
        self.console.print("[dim]Dashboard refreshes every 5 seconds...[/dim]")
        self.console.print("[dim]Press Ctrl+C to exit[/dim]\n")

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
                    new_trades = self.ingest_live_data()

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
