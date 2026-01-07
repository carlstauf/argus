# ARGUS Command Center - Web Application

The production-grade web interface for ARGUS, featuring a clean dark-mode financial terminal aesthetic.

## Architecture

### Backend (FastAPI)
- **Location**: `/api/server.py`
- **WebSocket Endpoint**: `ws://localhost:8000/ws/live` - Real-time trade and alert streaming
- **REST API**:
  - `GET /api/stats` - System statistics
  - `GET /api/history` - Trade history
  - `GET /api/wallets` - Wallet data
  - `GET /api/wallets/{address}` - Wallet details
  - `GET /api/alerts` - Intelligence alerts
  - `GET /api/markets` - Active markets

### Frontend (Next.js 14)
- **Location**: `/web`
- **Framework**: Next.js 14 with App Router
- **Styling**: Tailwind CSS with custom Zinc palette
- **UI Components**: Shadcn/UI
- **Data Grid**: TanStack Table for high-velocity updates

## Design System

### Color Palette
- **Background**: Zinc-950 (Deep dark)
- **Borders**: Zinc-800 (Discrete)
- **Text**: Zinc-50 (High contrast)
- **Semantic Colors**:
  - Buy: Emerald-400 (#34d399)
  - Sell: Rose-500 (#f43f5e)
  - Alerts: Amber-400 (#fbbf24)

### Typography
- **Font**: Geist Mono (monospace for all text)
- **Style**: Clean, terminal-inspired

### Effects
- **Glassmorphism**: Panels use `bg-zinc-900/60 backdrop-blur-md`
- **Animations**: Smooth transitions, pulse effects for live indicators

## Setup

### Backend

1. Install Python dependencies:
```bash
cd api
pip install -r requirements.txt
```

2. Ensure PostgreSQL is running and `.env` is configured:
```bash
DATABASE_URL=postgresql://user:password@localhost:5432/argus
```

3. Start the FastAPI server:
```bash
python server.py
```

The backend will be available at `http://localhost:8000`

### Frontend

1. Install Node.js dependencies:
```bash
cd web
npm install
```

2. Start the Next.js development server:
```bash
npm run dev
```

The frontend will be available at `http://localhost:3000`

## Running ARGUS Command Center

### Full Stack (Recommended)

Terminal 1 - Backend:
```bash
cd api
python server.py
```

Terminal 2 - Frontend:
```bash
cd web
npm run dev
```

Then open `http://localhost:3000` in your browser.

## Features

### 1. Top Bar - Global Market Stats
- Real-time market statistics
- Connection status indicator
- Alert counter

### 2. The Panopticon Table
- High-velocity trade table with TanStack Table
- Sortable columns
- Alert highlighting
- Smooth animations for new trades

### 3. Live Feed
- Real-time trade stream
- Color-coded buy/sell indicators
- Alert badges for suspicious activity

### 4. Intelligence Alerts Stream
- Real-time alerts from the Intelligence Engine
- Severity-based color coding (CRITICAL, HIGH, MEDIUM, LOW)
- Confidence scores
- Wallet tracking

## WebSocket Protocol

### Client → Server
```json
"ping"
```

### Server → Client

**Init Message** (on connection):
```json
{
  "type": "init",
  "trades": [...],
  "alerts": [...]
}
```

**New Trade**:
```json
{
  "type": "trade",
  "data": {
    "tx_hash": "0x...",
    "wallet": "0x...",
    "side": "BUY",
    "value_usd": 1000,
    "market": "Will...",
    "timestamp": "2024-01-01T00:00:00",
    "is_alert": false
  }
}
```

**New Alert**:
```json
{
  "type": "alert",
  "data": {
    "id": "...",
    "severity": "CRITICAL",
    "title": "Fresh Wallet Alert",
    "confidence": 0.95,
    "timestamp": "2024-01-01T00:00:00"
  }
}
```

**Stats Update**:
```json
{
  "type": "stats",
  "data": {
    "total_wallets": 1000,
    "total_trades": 5000,
    "active_markets": 100,
    "unread_alerts": 5
  }
}
```

## Production Deployment

### Backend
- Use `uvicorn` with Gunicorn for production
- Enable SSL/TLS for WebSocket connections (wss://)
- Configure CORS for your frontend domain

### Frontend
- Build for production: `npm run build`
- Deploy to Vercel, Netlify, or any Node.js hosting
- Update `NEXT_PUBLIC_WS_URL` to production WebSocket URL

### Environment Variables

**Backend (.env)**:
```
DATABASE_URL=postgresql://...
FRESH_WALLET_HOURS=72
WHALE_THRESHOLD_USD=1000
```

**Frontend (.env.local)**:
```
NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws/live
NEXT_PUBLIC_API_URL=http://localhost:8000/api
```

## Customization

### Adding New Dashboard Panels
1. Create component in `/web/components/dashboard/`
2. Add to Bento Grid in `/web/app/page.tsx`
3. Connect to WebSocket hook or REST API

### Modifying Color Scheme
Edit `/web/tailwind.config.ts` and `/web/app/globals.css`

### Adding New API Endpoints
Edit `/api/server.py` and add route handlers

## Performance

- **WebSocket**: Auto-reconnect with exponential backoff
- **Table**: Virtualized rendering for 1000+ rows
- **Caching**: Component-level memoization
- **Bundle Size**: Code-split by route

## Browser Support
- Chrome/Edge: Full support
- Firefox: Full support
- Safari: Full support (WebSocket reconnection may be slower)

## Troubleshooting

**WebSocket won't connect**:
- Ensure backend is running on port 8000
- Check browser console for errors
- Verify CORS settings in server.py

**Trades not updating**:
- Check database connection
- Verify Polymarket API is accessible
- Check backend logs for ingestion errors

**Styling issues**:
- Run `npm run build` to check for Tailwind errors
- Ensure dark mode is enabled in layout.tsx

---

Built with 👁️ by the ARGUS team
