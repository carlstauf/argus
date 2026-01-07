# ARGUS Intelligence Algorithms

**The Science Behind the Signal**

This document explains the core intelligence algorithms that power ARGUS.

---

## Philosophy

> **"Information Asymmetry is the only edge."**

ARGUS doesn't predict markets. It detects when **someone else** knows something the market hasn't priced in yet.

### The Three Types of Alpha

1. **Timing Alpha**: Trading BEFORE news breaks (insider knowledge)
2. **Structure Alpha**: Detecting manipulation (spoofing, wash trading)
3. **Sentiment Alpha**: News sentiment vs. market odds (reality gaps)

---

## Core Algorithms

### 1. The Freshness Index (Insider Detection)

**Hypothesis:** Brand-new wallets making large bets have insider knowledge.

**Algorithm:**
```python
freshness_score = f(wallet_age_hours)

if wallet_age_hours < 1:
    score = 100  # EXTREME
elif wallet_age_hours < 24:
    score = 90   # CRITICAL
elif wallet_age_hours < 168:  # 1 week
    score = 70   # HIGH
elif wallet_age_hours < 720:  # 1 month
    score = 40   # MEDIUM
elif wallet_age_hours < 8760:  # 1 year
    score = 10   # LOW
else:
    score = 0    # ANCIENT
```

**Alert Trigger:**
```
IF freshness_score >= 90 AND trade_value_usd > $5,000:
    ALERT: CRITICAL - INSIDER SIGNAL
```

**Why This Works:**
- Insiders don't want to use their main wallet (it can be traced)
- They create fresh "burner" wallets for specific trades
- If a brand-new wallet immediately makes a $10k bet, they likely KNOW something

**Real Example:**
```
Wallet: 0x88a3d4...
Created: 2026-01-06 10:00:00
First Trade: 2026-01-06 10:15:00 (15 minutes later)
Amount: $8,500 on "Trump wins 2024"
Resolution: Market resolves YES 2 hours later
Result: Wallet wins $8,500 → 100% ROI in 2 hours

Verdict: INSIDER
```

---

### 2. The Pre-News Signal (Timeline Analysis)

**Hypothesis:** Wallets that consistently trade BEFORE news breaks have inside information.

**Algorithm:**
```sql
-- For each trade, calculate time distance to nearest news event
news_distance_seconds = trade_timestamp - news_timestamp

-- Negative = trade happened BEFORE news
-- Positive = trade happened AFTER news (reactive)

-- Flag wallets with pattern of pre-news trading
SELECT wallet_address, COUNT(*) as suspicious_trades
FROM trades
WHERE news_distance_seconds < 0  -- BEFORE news
  AND ABS(news_distance_seconds) < 3600  -- Within 1 hour
GROUP BY wallet_address
HAVING COUNT(*) >= 3
```

**Alert Trigger:**
```
IF wallet has >= 3 trades BEFORE news events:
    insider_confidence_score = 0.85
    ALERT: HIGH - INSIDER PATTERN DETECTED
```

**Visualization:**
```
Timeline:
10:00 AM ────────── 10:30 AM ────────── 11:00 AM ────────── 11:30 AM
         │                     │                     │
         │                     │                     │
    Wallet 0x88...         News breaks:          Market reacts
    Buys $5k YES       "Trump announces VP"     Price: 0.45 → 0.75
                       (10:32 AM)
         │                     │
         └─────────────────────┘
           32 minutes EARLY
           = INSIDER SIGNAL
```

---

### 3. Statistical Anomaly Detection (Outlier Identification)

**Hypothesis:** Trades that are statistical outliers may indicate insider knowledge.

**Algorithm:**
```python
# For each market, calculate:
avg_trade_size = MEAN(trade_sizes_last_7_days)
stddev_trade_size = STDDEV(trade_sizes_last_7_days)

# For each new trade:
sigma_distance = (trade_size - avg_trade_size) / stddev_trade_size

# Flag if > 2σ (2 standard deviations)
if sigma_distance > 2.0:
    is_anomalous = TRUE
    ALERT: MEDIUM - STATISTICAL ANOMALY
```

**Example:**
```
Market: "Will Biden win 2024?"
Avg trade size: $250
Stddev: $100

New trade: $1,500
Sigma distance: (1500 - 250) / 100 = 12.5σ

Result: EXTREME ANOMALY → ALERT
```

**Why This Works:**
- Insiders bet BIG because they're certain
- Retail bets are typically small ($50-$500)
- A $10k bet in a market with $200 average? Someone knows something.

---

### 4. The Copy Leaderboard (Smart Money Tracking)

**Hypothesis:** Some wallets consistently win. Copy their strategy.

**Scoring Algorithm:**
```python
copy_score = (
    win_rate * 30 +           # 30% weight on win rate
    roi_pct * 25 +            # 25% weight on ROI
    sharpe_ratio * 20 +       # 20% weight on risk-adjusted returns
    timing_bonus * 15 +       # 15% weight on entry timing
    consistency_bonus * 10    # 10% weight on consistency
)

# Timing Bonus: Do they enter close to resolution?
if avg_time_before_resolution < 24 hours:
    timing_bonus = 100  # "Sniper"
elif avg_time_before_resolution < 168 hours:
    timing_bonus = 50   # "Tactical"
else:
    timing_bonus = 0    # "Strategic"
```

**Trader Types:**
- **Sniper**: Enters < 24h before resolution (likely insider or has edge)
- **Tactical**: Enters 1-7 days before (reacts to news)
- **Strategic**: Enters weeks early (long-term conviction)

**Alert:**
```
IF copy_score > 80 AND trader_type == 'Sniper':
    ALERT: Follow this wallet closely (possible insider)
```

---

### 5. Reality Gap Detection (Sentiment Arbitrage)

**Hypothesis:** When news sentiment diverges from market odds, there's an arbitrage opportunity.

**Algorithm:**
```python
# Parse news headline
headline = "CONFIRMED: Biden wins election"
keywords = ['CONFIRMED', 'OFFICIAL', 'BREAKING']

# Calculate sentiment
if any(keyword in headline for keyword in keywords):
    sentiment_score = 0.99  # Highly confident YES
    confidence_score = 0.95 # Very confident

# Get market price
market_yes_price = 0.65  # Market says 65% chance

# Calculate gap
reality_gap = abs(sentiment_score - market_yes_price)
# = abs(0.99 - 0.65) = 0.34 (34% gap!)

# Signal
if reality_gap > 0.20 and confidence_score > 0.75:
    if sentiment_score > market_yes_price:
        SIGNAL: BUY YES (underpriced)
    else:
        SIGNAL: BUY NO (overpriced)
```

**Real Example:**
```
Headline: "OFFICIAL: Supreme Court overturns law"
Sentiment: 99% (confirmed YES)
Market Price: 58% YES
Gap: 41%

Action: BUY YES
Expected Return: ~71% profit (if market corrects to 99%)
```

---

### 6. The Whale Tracker (Position Monitoring)

**Definition:** A "whale" is a wallet with:
- Total PnL > $50,000, OR
- Single trade > $10,000, OR
- Total volume > $500,000

**Algorithm:**
```sql
-- Mark whales
UPDATE wallets SET is_whale = TRUE
WHERE total_pnl_usd > 50000
   OR total_volume_usd > 500000
   OR EXISTS (
       SELECT 1 FROM trades
       WHERE wallet_address = wallets.address
       AND value_usd > 10000
   )
```

**Alert Trigger:**
```
IF whale makes trade > $10,000:
    ALERT: HIGH - WHALE MOVEMENT
    Description: "Known whale [address] placed $X on [market]"
    Context: "Lifetime PnL: $Y | Win Rate: Z%"
```

**Why Track Whales:**
- They have capital to move markets
- They likely have better information (can afford premium sources)
- Their movements can signal market direction

---

### 7. Spoof Detection (Market Manipulation)

**Definition:** "Spoofing" is placing large fake orders to manipulate price, then canceling them.

**Algorithm:**
```python
# Track order book snapshots every 10 seconds
for order in order_book:
    if order.size > 10000:  # Large order
        track_order(order.id, order.price, order.size)

# 30 seconds later, check if still there
if order_disappeared and price_moved_toward_order:
    ALERT: SPOOF DETECTED
    Description: "Fake $X wall at price Y was pulled after Z seconds"
```

**Visual:**
```
Order Book at 10:00:00 AM:
BUY:  $50k @ 0.60  <-- LARGE WALL (makes it look like support)
BUY:  $2k @ 0.59
BUY:  $1k @ 0.58

Order Book at 10:00:30 AM:
BUY:  [REMOVED]    <-- Wall disappeared!
BUY:  $2k @ 0.59
BUY:  $1k @ 0.58

Result: Spoofer wanted to scare sellers, then pulled the order.
```

---

## Intelligence Score (Overall System)

Each wallet gets an **Intelligence Score** (0-100):

```python
intelligence_score = (
    insider_confidence_score * 40 +  # 40% - Most important
    copy_score * 30 +                # 30% - Profitability
    whale_bonus * 20 +               # 20% - Capital size
    consistency_bonus * 10           # 10% - Reliability
)
```

**Score Interpretation:**
- **90-100**: CRITICAL - Extremely likely insider
- **70-89**: HIGH - Strong signal, investigate
- **50-69**: MEDIUM - Worth monitoring
- **0-49**: LOW - Retail trader

---

## Alert Priority System

ARGUS generates alerts, but not all are equal.

**Alert Severity:**
```
CRITICAL (Score >= 90):
  • Fresh wallet + large bet
  • Consistent pre-news trading
  • Whale with 3+ insider signals

HIGH (Score 70-89):
  • Whale movement
  • Statistical anomaly (> 3σ)
  • Reality gap > 30%

MEDIUM (Score 50-69):
  • Moderate anomaly (> 2σ)
  • Spoof detected
  • Reality gap 20-30%

LOW (Score < 50):
  • Minor anomalies
  • Informational only
```

**Rate Limiting:**
- Max 5 alerts per hour (prevents spam)
- 15-minute cooldown between similar alerts
- User can adjust thresholds in config

---

## Future Enhancements

### Phase 2: Oracle (Event Correlation)
- Real-time news scraping (Twitter, Reuters, Bloomberg)
- NLP sentiment analysis
- Automatic market-to-news mapping

### Phase 3: Seismic (Market Structure)
- WebSocket order book streaming
- Liquidity depth analysis
- Spread anomaly detection

### Phase 4: Machine Learning
- Train models on historical insider patterns
- Predict probability of insider trading
- Automated threshold optimization

---

## Limitations & Disclaimers

**What ARGUS Can Do:**
- ✅ Detect unusual wallet behavior
- ✅ Identify timing anomalies
- ✅ Track profitable traders
- ✅ Find sentiment-price gaps

**What ARGUS Cannot Do:**
- ❌ Guarantee profits (markets are unpredictable)
- ❌ Confirm legal insider trading (correlation ≠ causation)
- ❌ Predict market outcomes
- ❌ Replace human judgment

**Legal Notice:**
This tool is for **educational and informational purposes only**.
Using insider information to trade is illegal.
ARGUS detects *patterns*, not proof of illegal activity.

---

## The Edge

The real edge isn't the algorithm. It's the **discipline**:

1. **Trust the signal** - If ARGUS says CRITICAL, pay attention
2. **Size appropriately** - Higher confidence = larger position
3. **Act fast** - Insider signals decay quickly
4. **Keep learning** - Markets adapt, so must you

**Remember:**
> "The market can stay irrational longer than you can stay solvent."
> — John Maynard Keynes

ARGUS gives you an edge. What you do with it is up to you. 👁️
