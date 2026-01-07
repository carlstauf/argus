# ARGUS Setup Guide

## Prerequisites

1. **PostgreSQL 14+**
   ```bash
   # macOS (via Homebrew)
   brew install postgresql@14
   brew services start postgresql@14

   # Ubuntu/Debian
   sudo apt-get install postgresql-14
   sudo systemctl start postgresql
   ```

2. **Python 3.11+**
   ```bash
   python3 --version  # Should be 3.11 or higher
   ```

---

## Installation Steps

### 1. Clone and Enter Directory
```bash
cd /Users/carlstauf/argus
```

### 2. Create Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment
```bash
# Copy example config
cp .env.example .env

# Edit .env with your settings
nano .env
```

**Required settings in `.env`:**
```bash
DATABASE_URL=postgresql://postgres:yourpassword@localhost:5432/argus
```

### 5. Create Database
```bash
# Connect to PostgreSQL
psql -U postgres

# Create the database
CREATE DATABASE argus;

# Exit
\q
```

### 6. Initialize Schema
```bash
python argus.py init
```

You should see:
```
✓ Database 'argus' created successfully
✓ Migration 001_initial_schema.sql completed successfully
Created 12 tables:
  ✓ wallets
  ✓ markets
  ✓ trades
  ...
```

---

## Usage

### Recommended: Launch LIVE Terminal 🔴
```bash
python argus.py live
```

This is the **Bloomberg-style real-time terminal**. It:
1. Loads initial data (markets + trades)
2. Starts live ingestion (every **2 seconds**)
3. Updates dashboard (every **5 seconds**)
4. Auto-detects insider signals in real-time

**The LIVE Terminal displays:**

```
┌─ ARGUS 👁️ Live Intelligence Terminal ────────────────────┐
│ Live @ 18:30:45 | Last update: 1s ago                    │
└───────────────────────────────────────────────────────────┘

┌─ 📊 LIVE TICKER ──────────────────┬─ Stats ────────────┐
│ Time     Wallet        Side Value │ Markets: 2,437     │
│ 18:30:43 0xb96c... BUY  $1,250   │ Wallets: 15,234    │
│ 18:30:41 0x88a3... SELL $520     │ Trades:  127,456   │
│ 18:30:39 0xfa20... BUY  $8,500 🚨│ Ingested: 1,234    │
├───────────────────────────────────┤ Alerts:  3         │
│ 🔴 THE PANOPTICON (Fresh Wallets)│                     │
│ Address     Age  Trades  Volume  ├─ 🚨 RECENT ALERTS ─┤
│ 0x88a3d...  3.2h    12   $15,230 │ CRITICAL: Insider  │
│ 0xb96c2...  12h      5   $8,100  │ HIGH: Whale moved  │
└───────────────────────────────────┴─────────────────────┘
```

**Features:**
- **Green/Red color coding** for BUY/SELL
- **🚨 Alert indicator** on suspicious trades
- **Auto-refreshing** (you see activity immediately)
- **No crashes** on duplicates (uses upserts)

Press `Ctrl+C` to exit.

---

### Alternative: Background Ingestion
```bash
# Run in background (separate process)
python argus.py ingest
```

This runs every 30 seconds (slower than live mode).

### Alternative: Static Dashboard
```bash
python argus.py dashboard
```

Static version that refreshes every 5 seconds.

### Run Intelligence Queries
```bash
# Fresh wallets with large bets (insider signals)
python argus.py query fresh

# Insider trading patterns
python argus.py query insider

# Copy leaderboard
python argus.py query copy

# Whale movements
python argus.py query whale

# Statistical anomalies
python argus.py query anomaly

# Reality gap opportunities
python argus.py query gap
```

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Polymarket APIs                    │
│  (Gamma API, Data API, CLOB API - No auth needed)  │
└────────────────┬────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────┐
│              Ingestor (Panopticon)                  │
│  • Fetches markets every 5 minutes                  │
│  • Fetches trades every 30 seconds                  │
│  • Detects anomalies in real-time                   │
│  • Generates alerts                                 │
└────────────────┬────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────┐
│              PostgreSQL Database                    │
│  • 12 tables (wallets, trades, markets, etc.)      │
│  • JSONB for flexible metadata                      │
│  • Materialized views for performance               │
└────────────────┬────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────┐
│              Dashboard & Queries                    │
│  • Real-time terminal UI                            │
│  • Pre-built intelligence queries                   │
│  • Alert monitoring                                 │
└─────────────────────────────────────────────────────┘
```

---

## Configuration

### Intelligence Thresholds (.env)

```bash
# How old is "fresh"? (hours)
FRESH_WALLET_HOURS=24

# Minimum bet to trigger whale alert (USD)
WHALE_THRESHOLD_USD=5000

# Statistical significance (standard deviations)
ANOMALY_SIGMA=2.0

# Minimum confidence for insider scoring
INSIDER_CONFIDENCE_MIN=0.75
```

---

## Troubleshooting

### Database Connection Error
```
Error: could not connect to server
```

**Solution:**
1. Check PostgreSQL is running: `brew services list` (macOS) or `systemctl status postgresql` (Linux)
2. Verify credentials in `.env`
3. Try connecting manually: `psql -U postgres`

### No Data in Dashboard
```
Dashboard shows 0 trades, 0 wallets
```

**Solution:**
1. Make sure ingestion is running: `python argus.py ingest`
2. Wait 1-2 minutes for initial data load
3. Check logs for errors

### Import Errors
```
ModuleNotFoundError: No module named 'requests'
```

**Solution:**
```bash
# Make sure you're in the virtual environment
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

---

## Next Steps

Once the system is running:

1. **Let it collect data for 1-2 hours**
   - The more data, the better the anomaly detection

2. **Monitor the dashboard**
   - Watch for CRITICAL and HIGH severity alerts
   - These are the highest-probability insider signals

3. **Run intelligence queries**
   - `query fresh` → New wallets making big bets
   - `query insider` → Wallets that trade before news
   - `query copy` → Best traders to follow

4. **Tune thresholds**
   - Adjust values in `.env` based on what you observe
   - Too many false positives? Increase `WHALE_THRESHOLD_USD`
   - Too few alerts? Decrease `ANOMALY_SIGMA`

---

## Advanced: Running as a Service

### Using systemd (Linux)

Create `/etc/systemd/system/argus-ingest.service`:
```ini
[Unit]
Description=ARGUS Ingestion Service
After=network.target postgresql.service

[Service]
Type=simple
User=youruser
WorkingDirectory=/path/to/argus
Environment=PATH=/path/to/argus/venv/bin
ExecStart=/path/to/argus/venv/bin/python argus.py ingest
Restart=always

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable argus-ingest
sudo systemctl start argus-ingest
```

### Using screen (Quick Method)

```bash
# Start ingestion in background
screen -S argus-ingest
source venv/bin/activate
python argus.py ingest
# Press Ctrl+A, then D to detach

# Start dashboard in another screen
screen -S argus-dashboard
source venv/bin/activate
python argus.py dashboard
# Press Ctrl+A, then D to detach

# Reattach anytime
screen -r argus-ingest
screen -r argus-dashboard
```

---

## Support

For issues, check:
1. Polymarket API status: https://status.polymarket.com
2. Database logs: Check PostgreSQL logs for connection issues
3. Python errors: Run with `python -v argus.py <command>` for verbose output
