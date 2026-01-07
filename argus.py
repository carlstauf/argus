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
    def polymarket_market_url(condition_id: str) -> str:
        """Generate Polymarket market URL"""
        return f"https://polymarket.com/market/{condition_id}"

    @staticmethod
    def etherscan_tx_url(tx_hash: str) -> str:
        """Generate Etherscan transaction URL"""
        return f"https://etherscan.io/tx/{tx_hash}"

    @staticmethod
    def etherscan_address_url(address: str) -> str:
        """Generate Etherscan address URL"""
        return f"https://etherscan.io/address/{address}"

    @staticmethod
    def polyscan_address_url(address: str) -> str:
        """Generate Polyscan address URL (Polymarket-specific)"""
        return f"https://polyscan.com/address/{address}"

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

                    # Commit before running intelligence analysis
                    self.db_conn.commit()

                    # Run Intelligence Engine analysis
                    is_alert = await self._run_intelligence_analysis(
                        wallet_address, condition_id, value_usd, timestamp, cursor
                    )

                    # Get market slug if available
                    cursor.execute("""
                        SELECT slug FROM markets WHERE condition_id = %s
                    """, (condition_id,))
                    market_slug = cursor.fetchone()
                    slug = market_slug[0] if market_slug and market_slug[0] else None

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
                        'slug': slug
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
        """Get fresh wallets with high volume"""
        cursor = self.db_conn.cursor()

        cursor.execute("""
            SELECT
                w.address,
                EXTRACT(EPOCH FROM (NOW() - w.first_seen_at)) / 3600 as age_hours,
                w.total_trades,
                w.total_volume_usd,
                w.freshness_score,
                w.total_pnl_usd,
                w.win_rate
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
        """Create enhanced header panel"""
        text = Text()
        text.append("ARGUS ", style="bold cyan")
        text.append("👁️ ", style="bold white")
        text.append("LIVE INTELLIGENCE TERMINAL", style="bold white")
        text.append(" v2.0", style="dim")

        # Status indicators
        status_text = Text()
        status_text.append("🟢 LIVE", style="bold green")
        status_text.append(" | ", style="dim")
        
        if self.last_ingest_time:
            seconds_ago = (datetime.now() - self.last_ingest_time).seconds
            if seconds_ago < 5:
                status_text.append(f"Updated {seconds_ago}s ago", style="green")
            elif seconds_ago < 15:
                status_text.append(f"Updated {seconds_ago}s ago", style="yellow")
            else:
                status_text.append(f"Updated {seconds_ago}s ago", style="red")
        else:
            status_text.append("Initializing...", style="dim")
        
        status_text.append(" | ", style="dim")
        status_text.append(f"{datetime.now().strftime('%H:%M:%S')}", style="cyan")

        subtitle = str(status_text)

        return Panel(
            text,
            style="bold cyan",
            subtitle=subtitle,
            box=box.DOUBLE_EDGE
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
            title="[bold cyan]📈 SYSTEM STATS[/bold cyan]",
            border_style="cyan",
            box=box.DOUBLE_EDGE
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

            # Wallet with link hint
            wallet_text = Text()
            wallet_short = trade['wallet']
            wallet_text.append(wallet_short, style="cyan")
            if trade.get('wallet_full'):
                wallet_text.append(" 🔗", style="dim")

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

            # Market with link
            market_text = Text()
            if trade.get('is_alert'):
                market_text.append("🚨 ", style="bold red")
            market_text.append(trade['title'][:45], style="white")
            if trade.get('condition_id'):
                market_text.append(" 🔗", style="dim cyan")

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

        # Add footer with link instructions
        footer = Text()
        footer.append("\n💡 ", style="dim")
        footer.append("Click wallet/market to open in browser", style="dim italic")
        footer.append(" | ", style="dim")
        footer.append("Ctrl+Click", style="bold dim")
        footer.append(" = ", style="dim")
        footer.append("Etherscan/Polymarket", style="dim cyan")

        return Panel(
            table,
            title="[bold green]📊 LIVE TICKER[/bold green]",
            subtitle=f"Last {len(self.trade_log)} trades • Real-time updates",
            border_style="green",
            box=box.DOUBLE_EDGE
        )

    def make_panopticon(self, wallets: List[Tuple]) -> Panel:
        """Create enhanced suspicious wallets table with links"""
        table = Table(
            show_header=True,
            header_style="bold red",
            box=box.SIMPLE,
            expand=True,
            show_lines=True
        )

        table.add_column("Address", width=22, style="cyan")
        table.add_column("Age", width=8, justify="right")
        table.add_column("Trades", width=7, justify="right")
        table.add_column("Volume", width=13, justify="right", style="green")
        table.add_column("P&L", width=10, justify="right")
        table.add_column("Fresh", width=7, justify="right")

        for wallet in wallets:
            address, age_hours, trades, volume, freshness, pnl, win_rate = wallet[:7]

            # Address with link hint
            address_text = Text()
            address_text.append(address[:18] + "...", style="cyan")
            address_text.append(" 🔗", style="dim")

            # Format age
            if age_hours < 1:
                age_str = f"{int(age_hours * 60)}m"
                age_style = "bold red"
            elif age_hours < 24:
                age_str = f"{age_hours:.1f}h"
                age_style = "yellow"
            else:
                age_str = f"{age_hours/24:.1f}d"
                age_style = None

            # P&L with color
            pnl_val = pnl if pnl else 0
            pnl_text = Text()
            if pnl_val > 0:
                pnl_text.append(f"+${pnl_val:,.0f}", style="green")
            elif pnl_val < 0:
                pnl_text.append(f"${pnl_val:,.0f}", style="red")
            else:
                pnl_text.append("--", style="dim")

            # Win rate badge
            win_rate_val = win_rate if win_rate else 0
            if win_rate_val >= 0.6:
                win_style = "green"
            elif win_rate_val >= 0.4:
                win_style = "yellow"
            else:
                win_style = "red"

            # Color by freshness
            row_style = "bold red" if freshness >= 90 else ("yellow" if freshness >= 70 else None)

            # Freshness with color
            fresh_text = Text()
            if freshness >= 90:
                fresh_text.append(str(freshness), style="bold red")
            elif freshness >= 70:
                fresh_text.append(str(freshness), style="yellow")
            else:
                fresh_text.append(str(freshness), style="white")

            table.add_row(
                address_text,
                Text(age_str, style=age_style),
                str(trades),
                Text(f"${volume:,.0f}", style="green"),
                pnl_text,
                fresh_text,
                style=row_style
            )

        if not wallets:
            table.add_row("No suspicious activity detected", "", "", "", "", "", style="dim")

        return Panel(
            table,
            title="[bold red]🔴 THE PANOPTICON (Fresh Wallets)[/bold red]",
            subtitle="Auto-refreshes every 5s • Click address for Etherscan",
            border_style="red",
            box=box.DOUBLE_EDGE
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

            # Links column
            links_text = Text()
            if wallet:
                links_text.append("👤", style="cyan")
            if condition_id:
                links_text.append(" 📊", style="green")
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
            title="[bold yellow]🚨 INTELLIGENCE ALERTS[/bold yellow]",
            subtitle=f"Last {len(alerts)} alerts • Click icons for links",
            border_style="yellow",
            box=box.DOUBLE_EDGE
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

        # Split right into stats, alerts, and footer
        layout["right"].split_column(
            Layout(name="stats", size=9),
            Layout(name="alerts", ratio=2),
            Layout(name="footer", size=4)
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
        layout["footer"].update(self.make_footer())

        return layout

    def make_footer(self) -> Panel:
        """Create footer with URL instructions and recent trade links"""
        content = Text()
        content.append("🔗 QUICK LINKS", style="bold cyan")
        content.append(" (Latest Trade)\n", style="dim")
        
        # Show URLs for most recent trade if available
        if self.trade_log:
            latest = list(self.trade_log)[-1]
            
            if latest.get('tx_hash'):
                tx_url = self.etherscan_tx_url(latest['tx_hash'])
                content.append("TX: ", style="dim")
                # Use Rich's link format for clickable URLs
                content.append(tx_url, style="cyan underline")
                content.append("\n", style="dim")
            
            if latest.get('condition_id'):
                market_url = self.polymarket_market_url(latest['condition_id'])
                content.append("Market: ", style="dim")
                content.append(market_url, style="green underline")
                content.append("\n", style="dim")
            
            if latest.get('wallet_full'):
                wallet_url = self.etherscan_address_url(latest['wallet_full'])
                content.append("Wallet: ", style="dim")
                content.append(wallet_url, style="yellow underline")
        else:
            content.append("No trades yet...", style="dim")
        
        content.append("\n\n💡 ", style="dim")
        content.append("Terminal links are clickable", style="dim italic")
        content.append(" | ", style="dim")
        content.append("Copy URLs to browser", style="dim italic")

        return Panel(
            content,
            title="[bold dim]🔗 LINKS[/bold dim]",
            border_style="dim",
            box=box.SIMPLE
        )

    def print_urls_for_trade(self, trade: Dict):
        """Print URLs for a trade (helper for debugging/access)"""
        if trade.get('tx_hash'):
            self.console.print(f"\n[cyan]Transaction:[/cyan] {self.etherscan_tx_url(trade['tx_hash'])}")
        if trade.get('wallet_full'):
            self.console.print(f"[cyan]Wallet (Etherscan):[/cyan] {self.etherscan_address_url(trade['wallet_full'])}")
            self.console.print(f"[cyan]Wallet (Polyscan):[/cyan] {self.polyscan_address_url(trade['wallet_full'])}")
        if trade.get('condition_id'):
            self.console.print(f"[cyan]Market:[/cyan] {self.polymarket_market_url(trade['condition_id'])}")

    # ============================================================
    # Main Live Loop
    # ============================================================

    async def run_live(self):
        """Run the live terminal"""

        self.console.print("\n[bold cyan]Starting LIVE Intelligence Terminal...[/bold cyan]\n")
        self.console.print("[dim]Ingesting data every 2 seconds...[/dim]")
        self.console.print("[dim]Dashboard refreshes every 5 seconds...[/dim]")
        self.console.print("[dim]Press Ctrl+C to exit[/dim]\n")
        self.console.print("[bold yellow]💡 TIP:[/bold yellow] URLs are shown with 🔗 icons")
        self.console.print("[dim]   Copy URLs from terminal or use terminal's link support[/dim]\n")

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
