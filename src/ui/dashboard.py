"""
ARGUS - Terminal Dashboard
The "Heads-Up Display" for Prediction Market Intelligence
"""

import os
import time
import psycopg2
from datetime import datetime, timedelta
from typing import List, Dict
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from dotenv import load_dotenv

load_dotenv()


class ArgusDashboard:
    """Real-time intelligence dashboard"""

    def __init__(self):
        self.console = Console()
        self.db_conn = psycopg2.connect(os.getenv('DATABASE_URL'))

    def close(self):
        if self.db_conn:
            self.db_conn.close()

    # ============================================================
    # Data Fetchers
    # ============================================================

    def get_recent_alerts(self, limit: int = 10) -> List[Dict]:
        """Fetch recent unread alerts"""
        cursor = self.db_conn.cursor()
        cursor.execute("""
            SELECT
                a.id,
                a.alert_type,
                a.severity,
                a.title,
                a.description,
                a.confidence_score,
                a.created_at,
                a.wallet_address,
                m.question
            FROM alerts a
            LEFT JOIN markets m ON a.condition_id = m.condition_id
            WHERE a.is_dismissed = FALSE
            ORDER BY a.created_at DESC
            LIMIT %s
        """, (limit,))

        results = cursor.fetchall()
        cursor.close()

        alerts = []
        for row in results:
            alerts.append({
                'id': row[0],
                'type': row[1],
                'severity': row[2],
                'title': row[3],
                'description': row[4],
                'confidence': row[5],
                'time': row[6],
                'wallet': row[7],
                'question': row[8]
            })

        return alerts

    def get_fresh_wallets(self, limit: int = 10) -> List[Dict]:
        """Get recently active fresh wallets"""
        cursor = self.db_conn.cursor()
        cursor.execute("""
            SELECT
                w.address,
                w.first_seen_at,
                w.total_trades,
                w.total_volume_usd,
                w.freshness_score,
                w.last_active_at
            FROM wallets w
            WHERE
                w.freshness_score >= 70
                AND w.total_volume_usd > 1000
            ORDER BY w.last_active_at DESC
            LIMIT %s
        """, (limit,))

        results = cursor.fetchall()
        cursor.close()

        wallets = []
        for row in results:
            wallets.append({
                'address': row[0],
                'first_seen': row[1],
                'trades': row[2],
                'volume': row[3],
                'freshness': row[4],
                'last_active': row[5]
            })

        return wallets

    def get_top_traders(self, limit: int = 10) -> List[Dict]:
        """Get copy-worthy traders"""
        cursor = self.db_conn.cursor()
        cursor.execute("""
            SELECT
                w.address,
                w.total_trades,
                w.total_volume_usd,
                w.total_pnl_usd,
                w.win_rate,
                wp.copy_score,
                wp.roi_pct
            FROM wallets w
            LEFT JOIN wallet_profiles wp ON w.address = wp.wallet_address
            WHERE w.total_trades >= 5
            ORDER BY wp.copy_score DESC NULLS LAST
            LIMIT %s
        """, (limit,))

        results = cursor.fetchall()
        cursor.close()

        traders = []
        for row in results:
            traders.append({
                'address': row[0],
                'trades': row[1],
                'volume': row[2],
                'pnl': row[3],
                'win_rate': row[4],
                'copy_score': row[5],
                'roi': row[6]
            })

        return traders

    def get_stats(self) -> Dict:
        """Get system statistics"""
        cursor = self.db_conn.cursor()

        # Total counts
        cursor.execute("SELECT COUNT(*) FROM wallets")
        total_wallets = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM trades")
        total_trades = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM markets WHERE status = 'ACTIVE'")
        active_markets = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM alerts WHERE is_read = FALSE")
        unread_alerts = cursor.fetchone()[0]

        # Recent activity (last hour)
        cursor.execute("""
            SELECT COUNT(*) FROM trades
            WHERE executed_at > NOW() - INTERVAL '1 hour'
        """)
        recent_trades = cursor.fetchone()[0]

        cursor.close()

        return {
            'total_wallets': total_wallets,
            'total_trades': total_trades,
            'active_markets': active_markets,
            'unread_alerts': unread_alerts,
            'recent_trades_1h': recent_trades
        }

    # ============================================================
    # UI Renderers
    # ============================================================

    def render_header(self) -> Panel:
        """Render the header panel"""
        header_text = Text()
        header_text.append("ARGUS ", style="bold cyan")
        header_text.append("👁️  ", style="bold white")
        header_text.append("The All-Seeing Intelligence Layer", style="italic white")

        return Panel(
            header_text,
            style="bold cyan",
            subtitle=f"Live @ {datetime.now().strftime('%H:%M:%S')}"
        )

    def render_stats(self, stats: Dict) -> Table:
        """Render system statistics"""
        table = Table(title="System Stats", show_header=False, box=None)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green", justify="right")

        table.add_row("Active Markets", f"{stats['active_markets']:,}")
        table.add_row("Total Wallets", f"{stats['total_wallets']:,}")
        table.add_row("Total Trades", f"{stats['total_trades']:,}")
        table.add_row("Trades (1h)", f"{stats['recent_trades_1h']:,}")
        table.add_row("Unread Alerts", f"{stats['unread_alerts']:,}", style="yellow bold")

        return table

    def render_alerts(self, alerts: List[Dict]) -> Table:
        """Render alerts table"""
        table = Table(title="🚨 RECENT ALERTS", show_header=True, expand=True)

        table.add_column("Time", style="dim", width=8)
        table.add_column("Type", style="cyan", width=15)
        table.add_column("Severity", width=10)
        table.add_column("Alert", style="white")
        table.add_column("Conf", justify="right", width=6)

        for alert in alerts[:10]:
            # Color severity
            severity_style = {
                'CRITICAL': 'bold red',
                'HIGH': 'bold yellow',
                'MEDIUM': 'bold blue',
                'LOW': 'dim'
            }.get(alert['severity'], 'white')

            # Time ago
            time_ago = datetime.now() - alert['time']
            if time_ago.seconds < 60:
                time_str = f"{time_ago.seconds}s"
            elif time_ago.seconds < 3600:
                time_str = f"{time_ago.seconds // 60}m"
            else:
                time_str = f"{time_ago.seconds // 3600}h"

            # Truncate title
            title = alert['title'][:60] + "..." if len(alert['title']) > 60 else alert['title']

            table.add_row(
                time_str,
                alert['type'],
                alert['severity'],
                title,
                f"{alert['confidence']*100:.0f}%",
                style=severity_style if alert['severity'] in ['CRITICAL', 'HIGH'] else None
            )

        return table

    def render_fresh_wallets(self, wallets: List[Dict]) -> Table:
        """Render fresh wallets (PANOPTICON)"""
        table = Table(title="🔴 FRESH WALLETS (< 48h old)", show_header=True, expand=True)

        table.add_column("Address", style="cyan", width=12)
        table.add_column("Age", width=8)
        table.add_column("Trades", justify="right", width=8)
        table.add_column("Volume", justify="right", width=12)
        table.add_column("Fresh", justify="right", width=8)

        for wallet in wallets[:10]:
            age = datetime.now() - wallet['first_seen']
            if age.seconds < 3600:
                age_str = f"{age.seconds // 60}m"
            else:
                age_str = f"{age.seconds // 3600}h"

            # Color by freshness
            fresh_style = "bold red" if wallet['freshness'] >= 90 else "yellow"

            table.add_row(
                wallet['address'][:12] + "...",
                age_str,
                str(wallet['trades']),
                f"${wallet['volume']:,.0f}",
                f"{wallet['freshness']}",
                style=fresh_style if wallet['freshness'] >= 90 else None
            )

        return table

    def render_leaderboard(self, traders: List[Dict]) -> Table:
        """Render copy leaderboard"""
        table = Table(title="🏆 COPY LEADERBOARD", show_header=True, expand=True)

        table.add_column("Rank", justify="right", width=6)
        table.add_column("Address", style="cyan", width=12)
        table.add_column("Trades", justify="right", width=8)
        table.add_column("Win%", justify="right", width=8)
        table.add_column("ROI%", justify="right", width=10)
        table.add_column("Score", justify="right", width=8)

        for i, trader in enumerate(traders[:10], 1):
            win_rate = trader['win_rate'] or 0
            roi = trader['roi'] or 0
            score = trader['copy_score'] or 0

            # Highlight top 3
            style = None
            if i == 1:
                style = "bold gold1"
            elif i == 2:
                style = "bold grey74"
            elif i == 3:
                style = "bold dark_orange3"

            table.add_row(
                f"#{i}",
                trader['address'][:12] + "...",
                str(trader['trades']),
                f"{win_rate*100:.1f}%",
                f"{roi:.1f}%",
                str(score),
                style=style
            )

        return table

    # ============================================================
    # Main Dashboard
    # ============================================================

    def render_dashboard(self) -> Layout:
        """Render the complete dashboard"""
        layout = Layout()

        # Get data
        stats = self.get_stats()
        alerts = self.get_recent_alerts(limit=10)
        fresh_wallets = self.get_fresh_wallets(limit=10)
        traders = self.get_top_traders(limit=10)

        # Build layout
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body")
        )

        layout["header"].update(self.render_header())

        layout["body"].split_row(
            Layout(name="left"),
            Layout(name="right")
        )

        layout["left"].split_column(
            Layout(self.render_stats(stats), name="stats", size=9),
            Layout(self.render_alerts(alerts), name="alerts")
        )

        layout["right"].split_column(
            Layout(self.render_fresh_wallets(fresh_wallets), name="fresh"),
            Layout(self.render_leaderboard(traders), name="leaderboard")
        )

        return layout

    def run(self, refresh_seconds: int = 5):
        """Run the live dashboard"""
        try:
            with Live(self.render_dashboard(), refresh_per_second=1, console=self.console) as live:
                while True:
                    time.sleep(refresh_seconds)
                    live.update(self.render_dashboard())

        except KeyboardInterrupt:
            self.console.print("\n\n[bold cyan]ARGUS Dashboard shutting down... 👁️[/bold cyan]\n")
            self.close()


if __name__ == "__main__":
    dashboard = ArgusDashboard()
    dashboard.run(refresh_seconds=5)
