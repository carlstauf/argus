"""
ARGUS FastAPI Server
The Command Center Backend
"""

import os
import sys
import asyncio
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import deque

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from intelligence.engine import IntelligenceEngine
from api.polymarket_client import PolymarketClient
from api.ingestor import ArgusIngestor

load_dotenv()

# ============================================================
# FastAPI App
# ============================================================

app = FastAPI(
    title="ARGUS Command Center",
    description="The All-Seeing Intelligence Layer API",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# Database Connection
# ============================================================

def get_db_connection():
    """Get database connection"""
    return psycopg2.connect(
        os.getenv('DATABASE_URL'),
        cursor_factory=RealDictCursor
    )


# ============================================================
# WebSocket Manager
# ============================================================

class ConnectionManager:
    """Manage WebSocket connections for real-time streaming"""

    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.trade_buffer = deque(maxlen=100)
        self.alert_buffer = deque(maxlen=50)

    async def connect(self, websocket: WebSocket):
        """Accept new WebSocket connection"""
        await websocket.accept()
        self.active_connections.append(websocket)

        # Send buffered data to new client
        await websocket.send_json({
            "type": "init",
            "trades": list(self.trade_buffer),
            "alerts": list(self.alert_buffer)
        })

    def disconnect(self, websocket: WebSocket):
        """Remove WebSocket connection"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: Dict):
        """Broadcast message to all connected clients"""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)

        # Clean up disconnected clients
        for connection in disconnected:
            self.disconnect(connection)

    async def send_trade(self, trade: Dict):
        """Send new trade to all clients"""
        self.trade_buffer.append(trade)
        await self.broadcast({
            "type": "trade",
            "data": trade
        })

    async def send_alert(self, alert: Dict):
        """Send new alert to all clients"""
        self.alert_buffer.append(alert)
        await self.broadcast({
            "type": "alert",
            "data": alert
        })

    async def send_stats(self, stats: Dict):
        """Send stats update to all clients"""
        await self.broadcast({
            "type": "stats",
            "data": stats
        })


manager = ConnectionManager()


# ============================================================
# Background Task: Live Data Ingestion
# ============================================================

class LiveIngestionEngine:
    """Real-time data ingestion and intelligence analysis"""

    def __init__(self):
        self.db_conn = get_db_connection()
        self.intelligence = IntelligenceEngine(self.db_conn)
        self.polymarket_client = PolymarketClient()
        self.seen_trades = set()
        self.is_running = False

    async def start(self):
        """Start live ingestion loop"""
        self.is_running = True

        while self.is_running:
            try:
                await self.ingest_cycle()
                await asyncio.sleep(2)  # Ingest every 2 seconds
            except Exception as e:
                print(f"[ERROR] Ingestion cycle failed: {e}")
                await asyncio.sleep(5)

    async def ingest_cycle(self):
        """Single ingestion cycle"""
        # Fetch latest trades from Polymarket
        trades = self.polymarket_client.get_trades(limit=50)

        if not trades:
            return

        cursor = self.db_conn.cursor()
        new_trades_count = 0
        new_alerts_count = 0

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
                # Ensure wallet exists
                cursor.execute("""
                    INSERT INTO wallets (address, first_seen_at, last_active_at)
                    VALUES (%s, NOW(), NOW())
                    ON CONFLICT (address) DO UPDATE SET
                        last_active_at = NOW()
                """, (wallet_address,))

                # Ensure market exists
                cursor.execute("""
                    INSERT INTO markets (condition_id, question, status)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (condition_id) DO NOTHING
                """, (condition_id, trade.get('title', 'Unknown Market'), 'ACTIVE'))

                # Insert trade
                timestamp = trade.get('timestamp', int(datetime.now().timestamp()))
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
                    new_trades_count += 1

                    # Update wallet stats
                    cursor.execute("""
                        UPDATE wallets SET
                            total_trades = total_trades + 1,
                            total_volume_usd = total_volume_usd + %s
                        WHERE address = %s
                    """, (value_usd, wallet_address))

                    # Commit before intelligence analysis
                    self.db_conn.commit()

                    # Run Intelligence Engine
                    alerts = await self.intelligence.analyze({
                        'wallet_address': wallet_address,
                        'condition_id': condition_id,
                        'value_usd': value_usd,
                        'timestamp': timestamp
                    })

                    # Save and broadcast alerts
                    is_alert = False
                    for alert in alerts:
                        if self.intelligence.save_alert(alert):
                            new_alerts_count += 1
                            is_alert = True

                            # Broadcast alert to WebSocket clients
                            await manager.send_alert({
                                'id': alert.get('alert_type'),
                                'type': alert.get('alert_type'),
                                'severity': alert.get('severity'),
                                'title': alert.get('title'),
                                'description': alert.get('description'),
                                'confidence': alert.get('confidence_score'),
                                'wallet': wallet_address,
                                'timestamp': executed_at.isoformat()
                            })

                    # Broadcast trade to WebSocket clients
                    await manager.send_trade({
                        'tx_hash': tx_hash,
                        'wallet': wallet_address,
                        'wallet_short': wallet_address[:10] + '...',
                        'side': trade.get('side', 'BUY'),
                        'outcome': trade.get('outcome', 'Yes'),
                        'size': size,
                        'price': price,
                        'value_usd': value_usd,
                        'market': trade.get('title', 'Unknown')[:60],
                        'timestamp': executed_at.isoformat(),
                        'is_alert': is_alert
                    })

            except Exception as e:
                self.db_conn.rollback()
                print(f"[ERROR] Failed to process trade {tx_hash}: {e}")
                continue

        self.db_conn.commit()
        cursor.close()

        # Broadcast stats update every cycle
        if new_trades_count > 0:
            stats = await self.get_system_stats()
            await manager.send_stats(stats)

    async def get_system_stats(self) -> Dict:
        """Get current system stats"""
        cursor = self.db_conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM wallets")
        total_wallets = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(*) FROM trades")
        total_trades = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(*) FROM markets WHERE status = 'ACTIVE'")
        active_markets = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(*) FROM alerts WHERE is_read = FALSE")
        unread_alerts = cursor.fetchone()['count']

        cursor.execute("SELECT SUM(total_volume_usd) FROM markets WHERE status = 'ACTIVE'")
        total_volume = cursor.fetchone()['sum'] or 0

        cursor.close()

        return {
            'total_wallets': total_wallets,
            'total_trades': total_trades,
            'active_markets': active_markets,
            'unread_alerts': unread_alerts,
            'total_volume_usd': float(total_volume)
        }

    def stop(self):
        """Stop ingestion loop"""
        self.is_running = False


# Global ingestion engine
ingestion_engine = None


# ============================================================
# WebSocket Endpoint
# ============================================================

@app.websocket("/ws/live")
async def websocket_live(websocket: WebSocket):
    """
    WebSocket endpoint for live trade and alert streaming
    """
    await manager.connect(websocket)

    try:
        while True:
            # Keep connection alive (client can send pings)
            data = await websocket.receive_text()

            # Handle client commands if needed
            if data == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        manager.disconnect(websocket)


# ============================================================
# REST Endpoints
# ============================================================

@app.get("/api/stats")
async def get_stats():
    """Get system statistics"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM wallets")
    total_wallets = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) FROM trades")
    total_trades = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) FROM markets WHERE status = 'ACTIVE'")
    active_markets = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) FROM alerts WHERE is_read = FALSE")
    unread_alerts = cursor.fetchone()['count']

    cursor.execute("SELECT SUM(total_volume_usd) FROM markets WHERE status = 'ACTIVE'")
    total_volume = cursor.fetchone()['sum'] or 0

    cursor.close()
    conn.close()

    return {
        'total_wallets': total_wallets,
        'total_trades': total_trades,
        'active_markets': active_markets,
        'unread_alerts': unread_alerts,
        'total_volume_usd': float(total_volume),
        'timestamp': datetime.now().isoformat()
    }


@app.get("/api/history")
async def get_history(limit: int = 100, offset: int = 0):
    """Get trade history"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            t.transaction_hash,
            t.wallet_address,
            t.side,
            t.outcome,
            t.size,
            t.price,
            t.value_usd,
            t.executed_at,
            m.question as market
        FROM trades t
        LEFT JOIN markets m ON t.condition_id = m.condition_id
        ORDER BY t.executed_at DESC
        LIMIT %s OFFSET %s
    """, (limit, offset))

    trades = cursor.fetchall()
    cursor.close()
    conn.close()

    return {
        'trades': [dict(trade) for trade in trades],
        'count': len(trades)
    }


@app.get("/api/wallets")
async def get_wallets(limit: int = 50, sort: str = "freshness"):
    """Get wallet data sorted by various metrics"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Determine sort field
    sort_fields = {
        'freshness': 'freshness_score DESC, total_volume_usd DESC',
        'volume': 'total_volume_usd DESC',
        'trades': 'total_trades DESC',
        'pnl': 'total_pnl_usd DESC'
    }

    sort_sql = sort_fields.get(sort, sort_fields['freshness'])

    cursor.execute(f"""
        SELECT
            address,
            EXTRACT(EPOCH FROM (NOW() - first_seen_at)) / 3600 as age_hours,
            total_trades,
            total_volume_usd,
            total_pnl_usd,
            win_rate,
            freshness_score,
            is_whale,
            last_active_at
        FROM wallets
        WHERE total_volume_usd > 100
        ORDER BY {sort_sql}
        LIMIT %s
    """, (limit,))

    wallets = cursor.fetchall()
    cursor.close()
    conn.close()

    return {
        'wallets': [dict(wallet) for wallet in wallets],
        'count': len(wallets)
    }


@app.get("/api/wallets/{address}")
async def get_wallet_detail(address: str):
    """Get detailed wallet information"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Wallet info
    cursor.execute("""
        SELECT
            address,
            EXTRACT(EPOCH FROM (NOW() - first_seen_at)) / 3600 as age_hours,
            total_trades,
            total_volume_usd,
            total_pnl_usd,
            win_rate,
            freshness_score,
            is_whale,
            first_seen_at,
            last_active_at
        FROM wallets
        WHERE address = %s
    """, (address,))

    wallet = cursor.fetchone()
    if not wallet:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Wallet not found")

    # Recent trades
    cursor.execute("""
        SELECT
            t.transaction_hash,
            t.side,
            t.outcome,
            t.value_usd,
            t.executed_at,
            m.question as market
        FROM trades t
        LEFT JOIN markets m ON t.condition_id = m.condition_id
        WHERE t.wallet_address = %s
        ORDER BY t.executed_at DESC
        LIMIT 20
    """, (address,))

    trades = cursor.fetchall()

    cursor.close()
    conn.close()

    return {
        'wallet': dict(wallet),
        'recent_trades': [dict(trade) for trade in trades]
    }


@app.get("/api/alerts")
async def get_alerts(limit: int = 50, severity: Optional[str] = None):
    """Get recent alerts"""
    conn = get_db_connection()
    cursor = conn.cursor()

    if severity:
        cursor.execute("""
            SELECT
                id,
                alert_type,
                severity,
                wallet_address,
                condition_id,
                title,
                description,
                confidence_score,
                supporting_data,
                created_at,
                is_read
            FROM alerts
            WHERE severity = %s
            ORDER BY created_at DESC
            LIMIT %s
        """, (severity.upper(), limit))
    else:
        cursor.execute("""
            SELECT
                id,
                alert_type,
                severity,
                wallet_address,
                condition_id,
                title,
                description,
                confidence_score,
                supporting_data,
                created_at,
                is_read
            FROM alerts
            ORDER BY created_at DESC
            LIMIT %s
        """, (limit,))

    alerts = cursor.fetchall()
    cursor.close()
    conn.close()

    return {
        'alerts': [dict(alert) for alert in alerts],
        'count': len(alerts)
    }


@app.get("/api/markets")
async def get_markets(limit: int = 50):
    """Get active markets"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            condition_id,
            question,
            slug,
            category,
            total_volume_usd,
            current_liquidity_usd,
            status,
            end_date,
            updated_at
        FROM markets
        WHERE status = 'ACTIVE'
        ORDER BY total_volume_usd DESC
        LIMIT %s
    """, (limit,))

    markets = cursor.fetchall()
    cursor.close()
    conn.close()

    return {
        'markets': [dict(market) for market in markets],
        'count': len(markets)
    }


# ============================================================
# Startup & Shutdown
# ============================================================

@app.on_event("startup")
async def startup_event():
    """Start background ingestion on server startup"""
    global ingestion_engine

    print("\n" + "=" * 60)
    print("ARGUS COMMAND CENTER - INITIALIZING")
    print("=" * 60 + "\n")

    # Initialize database (run initial data load)
    print("[INIT] Running initial data load...")
    ingestor = ArgusIngestor()
    ingestor.ingest_markets()
    ingestor.ingest_trades(limit=200)
    ingestor.close()

    # Start live ingestion engine
    print("[INIT] Starting live ingestion engine...")
    ingestion_engine = LiveIngestionEngine()

    # Run in background
    asyncio.create_task(ingestion_engine.start())

    print("[INIT] ✓ ARGUS Command Center ONLINE")
    print("")


@app.on_event("shutdown")
async def shutdown_event():
    """Stop background ingestion on server shutdown"""
    global ingestion_engine

    if ingestion_engine:
        print("\n[SHUTDOWN] Stopping ingestion engine...")
        ingestion_engine.stop()

    print("[SHUTDOWN] ARGUS Command Center offline. 👁️\n")


# ============================================================
# Health Check
# ============================================================

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "ARGUS Command Center",
        "status": "online",
        "version": "2.0.0",
        "timestamp": datetime.now().isoformat()
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
