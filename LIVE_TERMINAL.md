# ARGUS LIVE Terminal 🔴

**The Bloomberg Experience for Prediction Markets**

---

## What Just Changed?

ARGUS has been upgraded from a **static script** to a **live, real-time intelligence terminal**.

### Before (Old):
- Run `python argus.py ingest` → polls every **30 seconds**
- Run `python argus.py query fresh` → prints table once and exits
- No live updates
- Crashes on duplicate data

### After (New): 🔴
- Run `python argus.py live` → polls every **2 seconds**
- **Persistent dashboard** that auto-refreshes every 5 seconds
- **Live ticker** showing trades as they happen
- **Bloomberg-style layout** with 4 panels
- **No crashes** (uses upserts)

---

## The New Command

```bash
python argus.py live
```

This launches a **4-panel dashboard**:

```
╔═══════════════════════════════════════════════════════╗
║              ARGUS 👁️ Live Intelligence Terminal      ║
║              Live @ 18:30:45 | Last update: 1s ago    ║
╚═══════════════════════════════════════════════════════╝

┌─────────────────────────────────────┬─────────────────┐
│ 📊 LIVE TICKER                      │ 📈 STATS        │
│ (Real-time trades scrolling)        │ Markets: 2,437  │
│                                     │ Wallets: 15,234 │
│ 18:30:43 0xb96c... BUY  $1,250     │ Trades:  127k   │
│ 18:30:41 0x88a3... SELL $520       │ Ingested: 1,234 │
│ 18:30:39 0xfa20... BUY  $8,500 🚨  │ Alerts: 3       │
├─────────────────────────────────────┤                 │
│ 🔴 THE PANOPTICON                   ├─────────────────┤
│ (Fresh wallets with activity)       │ 🚨 ALERTS       │
│                                     │                 │
│ 0x88a3d... 3.2h  12  $15,230       │ CRITICAL: ...   │
│ 0xb96c2... 12h    5  $8,100        │ HIGH: ...       │
└─────────────────────────────────────┴─────────────────┘
```

---

## The 4 Panels Explained

### Panel 1: 📊 LIVE TICKER (Top Left)
**What it shows:**
- Last 15 trades in real-time
- Updates every **2 seconds**

**Color coding:**
- 🟢 **Green** = BUY trades
- 🔴 **Red** = SELL trades

**Alert indicator:**
- 🚨 = Trade triggered a CRITICAL alert (fresh wallet + large bet)

**Columns:**
- `Time` - When the trade happened
- `Wallet` - Trader address (truncated)
- `Side` - BUY or SELL
- `Out` - Outcome (Yes/No)
- `Value` - Trade size in USD
- `Market` - Market title

---

### Panel 2: 🔴 THE PANOPTICON (Bottom Left)
**What it shows:**
- Fresh wallets (< 48h old) with significant activity
- Auto-refreshes every **5 seconds**

**Why this matters:**
- Brand-new wallets making big bets = **insider signal**
- Freshness score of 90+ = **CRITICAL**
- Freshness score of 70-89 = **HIGH**

**Color coding:**
- **Bold Red** = Freshness ≥ 90 (EXTREME RISK)
- **Yellow** = Freshness 70-89 (HIGH RISK)
- White = Freshness 50-69 (MEDIUM)

**Columns:**
- `Address` - Wallet address (truncated)
- `Age` - How old the wallet is (minutes/hours/days)
- `Trades` - Number of trades
- `Volume` - Total USD volume
- `Fresh` - Freshness score (0-100)

---

### Panel 3: 📈 STATS (Top Right)
**What it shows:**
- System-wide statistics

**Metrics:**
- `Markets` - Active markets in database
- `Wallets` - Total unique wallets tracked
- `Trades` - Total trades in database
- `Ingested` - Trades ingested this session
- `Alerts` - Unread CRITICAL/HIGH alerts

---

### Panel 4: 🚨 RECENT ALERTS (Bottom Right)
**What it shows:**
- Last 10 CRITICAL and HIGH severity alerts

**Alert Types:**
- **CRITICAL** = Freshness ≥ 90 + bet > $5,000
- **HIGH** = Whale movement or anomaly

**Columns:**
- `Sev` - Severity (CRITICAL/HIGH)
- `Alert` - Alert title
- `Conf` - Confidence score (0-100%)

---

## How the Ingestion Works

### The Faucet (Every 2 Seconds)

```python
def ingest_live_data():
    """Fetch and ingest new trades from Polymarket"""

    # 1. Fetch latest 50 trades from Polymarket API
    trades = client.get_trades(limit=50)

    # 2. For each trade:
    for trade in trades:
        # Skip if already seen
        if trade.hash in seen_trades:
            continue

        # 3. Upsert wallet (no crash on duplicates)
        INSERT INTO wallets ... ON CONFLICT DO UPDATE

        # 4. Upsert trade (no crash on duplicates)
        INSERT INTO trades ... ON CONFLICT DO NOTHING

        # 5. Update wallet stats
        UPDATE wallets SET total_trades = total_trades + 1

        # 6. Check for alerts
        if wallet_age < 24h AND trade_value > $5k:
            CREATE ALERT (CRITICAL)

        # 7. Add to live ticker
        trade_log.append(trade)

    # 8. Commit to database
    db.commit()
```

**Key improvements:**
- **ON CONFLICT DO NOTHING** = no crashes on duplicates
- **Cache of seen trades** = faster processing
- **Silent failures** = UI stays clean

---

## Alert Detection Logic

### CRITICAL: Fresh Wallet + Large Bet

```python
# Get wallet age
wallet_age_hours = NOW() - wallet.first_seen_at

# Check threshold
if wallet_age_hours < 24 and trade_value_usd > 5000:
    CREATE ALERT:
        Type: FRESH_WALLET
        Severity: CRITICAL
        Title: "🚨 INSIDER SIGNAL: $8,500 from 3.2h old wallet"
        Confidence: 85%
```

**Why this is powerful:**
- Insiders use burner wallets (fresh addresses)
- They bet big because they KNOW the outcome
- 85% confidence = extremely likely insider

---

## Keyboard Controls

- **Ctrl+C** - Exit the terminal gracefully

---

## Performance

**Before:**
- Ingestion: Every 30 seconds
- No live updates
- Static queries only

**After:**
- Ingestion: Every **2 seconds** (15x faster)
- Dashboard: Auto-refresh every **5 seconds**
- Live ticker: Updates instantly
- No lag, no crashes

---

## Troubleshooting

### "No trades appearing in ticker"

**Check:**
1. Is PostgreSQL running? `brew services list | grep postgresql`
2. Is the database initialized? `python argus.py init`
3. Are there trades on Polymarket? (Check polymarket.com)

**Wait time:**
- Initial load takes ~10 seconds
- First trades appear within 2-10 seconds
- If nothing after 30 seconds, check API connectivity

### "Table says 'No suspicious activity detected'"

**This is normal if:**
- No fresh wallets have made trades recently
- All wallets are > 48h old
- No large bets (> $5k) have been placed

**To test:**
- Lower the threshold in `.env`:
  ```
  FRESH_WALLET_HOURS=168  # 1 week instead of 24h
  WHALE_THRESHOLD_USD=100 # $100 instead of $5k
  ```

### "Dashboard is frozen"

**Possible causes:**
- Database connection lost
- API rate limit hit
- Network issue

**Fix:**
- Press Ctrl+C and restart: `python argus.py live`

---

## Comparison: Live vs. Other Modes

| Feature | `live` | `ingest` | `dashboard` | `query` |
|---------|--------|----------|-------------|---------|
| **Ingestion** | ✅ Every 2s | ✅ Every 30s | ❌ No | ❌ No |
| **Live Updates** | ✅ Yes | ❌ No | ⚠️  Every 5s | ❌ No |
| **Trade Ticker** | ✅ Yes | ❌ No | ❌ No | ❌ No |
| **Fresh Wallets** | ✅ Auto-refresh | ❌ No UI | ✅ Static | ✅ One-time |
| **Alerts** | ✅ Real-time | ⚠️  Console | ✅ Panel | ❌ No |
| **Performance** | ⚡ Fast | 🐢 Slow | 🐢 Slow | ⚡ Fast |
| **Best For** | **Production** | Background | Monitoring | Analysis |

**Recommendation:** Use `live` for 99% of use cases.

---

## Next Steps

1. **Launch the live terminal:**
   ```bash
   python argus.py live
   ```

2. **Watch for alerts:**
   - CRITICAL alerts = **highest priority**
   - Investigate fresh wallets immediately

3. **Export data:**
   - Use `python argus.py query fresh` to export to CSV
   - Analyze patterns over time

4. **Tune thresholds:**
   - Edit `.env` to adjust sensitivity
   - Lower `WHALE_THRESHOLD_USD` for more alerts
   - Increase for fewer (but higher quality) signals

---

## The Edge

The **live terminal** gives you a **time advantage**:

**Before (queries):**
- Fresh wallet makes $10k bet at 10:00 AM
- You run query at 10:30 AM
- **30 minutes late**

**After (live terminal):**
- Fresh wallet makes $10k bet at 10:00 AM
- Alert appears at 10:00:02 AM (2 seconds later)
- **You act immediately**

**That 30-minute gap is the difference between profit and missing the opportunity.**

---

**Welcome to the Bloomberg Terminal for Prediction Markets.** 👁️
