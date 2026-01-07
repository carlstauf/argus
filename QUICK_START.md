# ARGUS Quick Start Guide 🚀

## Prerequisites Check ✅

You need:
- ✅ Python 3.10+ (you have 3.10.18)
- ✅ PostgreSQL 14+ (you have 14.20)
- ✅ `.env` file configured

## Step-by-Step Start

### 1. Activate Virtual Environment (if using one)
```bash
cd /Users/carlstauf/argus
source venv/bin/activate  # If you have a venv
```

### 2. Install Dependencies (if not already done)
```bash
pip install -r requirements.txt
```

### 3. Check Database Connection
Make sure your `.env` file has:
```bash
DATABASE_URL=postgresql://postgres:yourpassword@localhost:5432/argus
```

### 4. Initialize Database (First Time Only)
```bash
python argus.py init
```

This creates all the tables. You should see:
```
✓ Database schema initialized
✓ Created 12 tables
```

### 5. Start the LIVE Terminal! 🔴
```bash
python argus.py live
```

That's it! The terminal will:
- Load initial data (markets + trades)
- Start ingesting new trades every 2 seconds
- Show a live dashboard with 5 panels
- Auto-detect insider signals

## What You'll See

```
╔═══════════════════════════════════════════════════════╗
║  ARGUS 👁️ LIVE INTELLIGENCE TERMINAL v2.0            ║
║  🟢 LIVE | Updated 2s ago | 18:30:45                  ║
╚═══════════════════════════════════════════════════════╝

┌─────────────────────────────────────┬─────────────────┐
│ 📊 LIVE TICKER                       │ 📈 SYSTEM STATS │
│ (Real-time trades with links 🔗)    │ Markets: 2,437  │
│                                      │ 24h Vol: $1.2M  │
│ 18:30:43 0xb96c...🔗 BUY  $1,250    │ Trades (1h): 45 │
│ 18:30:41 0x88a3...🔗 SELL $520      │ Ingested: 1,234 │
│ 18:30:39 0xfa20...🔗 BUY  $8,500🚨 │ Alerts: 3       │
├─────────────────────────────────────┤                 │
│ 🔴 THE PANOPTICON                    ├─────────────────┤
│ (Fresh wallets with P&L)             │ 🚨 ALERTS       │
│                                      │                 │
│ 0x88a3d...🔗 3.2h  12  $15k +$2k   │ 🔴 CRITICAL     │
│ 0xb96c2...🔗 12h   5  $8k  -$500    │ 🟡 HIGH         │
│                                      ├─────────────────┤
│                                      │ 🔗 QUICK LINKS  │
│                                      │ Latest Trade:   │
│                                      │ TX: etherscan...│
│                                      │ Market: poly... │
└─────────────────────────────────────┴─────────────────┘
```

## Other Commands

### Run Intelligence Queries
```bash
python argus.py query fresh      # Fresh wallets with large bets
python argus.py query insider    # Insider trading patterns
python argus.py query copy       # Copy leaderboard
python argus.py query whale      # Whale movements
python argus.py query anomaly    # Statistical anomalies
python argus.py query gap        # Reality gap opportunities
```

### Static Dashboard (Alternative)
```bash
python argus.py dashboard
```

### Background Ingestion
```bash
python argus.py ingest
```

## Troubleshooting

### "Database connection failed"
- Check your `.env` file has correct `DATABASE_URL`
- Make sure PostgreSQL is running: `brew services list | grep postgresql`
- Start PostgreSQL: `brew services start postgresql@14`

### "No trades appearing"
- Wait 10-30 seconds for initial data load
- Check Polymarket API is accessible
- Verify database has data: `psql -d argus -c "SELECT COUNT(*) FROM trades;"`

### "Module not found"
- Activate virtual environment: `source venv/bin/activate`
- Install dependencies: `pip install -r requirements.txt`

## Tips

- **Press Ctrl+C** to exit gracefully
- **Links are clickable** in modern terminals (iTerm2, Windows Terminal)
- **🔗 icons** indicate clickable items
- **Footer panel** shows URLs for latest trade
- **Alerts** appear in real-time when suspicious activity is detected

## Need Help?

See full documentation:
- `README.md` - Overview
- `SETUP.md` - Detailed setup
- `LIVE_TERMINAL.md` - Terminal features

---

**Ready? Run:** `python argus.py live` 🚀

