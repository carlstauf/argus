#!/usr/bin/env python3
"""
ARGUS - Polymarket API Reconnaissance
Tests connectivity and explores available data structures
"""

import requests
import json
from datetime import datetime

# API Base URLs
GAMMA_API = "https://gamma-api.polymarket.com"
DATA_API = "https://data-api.polymarket.com"

def test_gamma_markets():
    """Fetch active markets from Gamma API"""
    print("\n[1] Testing Gamma API - Markets Endpoint")
    print("=" * 60)

    try:
        url = f"{GAMMA_API}/markets"
        params = {
            "limit": 5,
            "active": True
        }

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        markets = response.json()
        print(f"✓ Success! Fetched {len(markets)} markets\n")

        if markets:
            market = markets[0]
            print("Sample Market Structure:")
            print(json.dumps(market, indent=2)[:1000] + "...\n")

            # Extract key fields
            print("Key Fields:")
            print(f"  - Market ID: {market.get('condition_id', 'N/A')}")
            print(f"  - Question: {market.get('question', 'N/A')}")
            print(f"  - Category: {market.get('category', 'N/A')}")
            print(f"  - Volume: ${market.get('volume', 0):,.2f}")
            print(f"  - Liquidity: ${market.get('liquidity', 0):,.2f}")

        return markets

    except Exception as e:
        print(f"✗ Error: {e}")
        return None


def test_data_trades(market_id=None):
    """Fetch recent trades from Data API"""
    print("\n[2] Testing Data API - Trades Endpoint")
    print("=" * 60)

    try:
        url = f"{DATA_API}/trades"
        params = {
            "limit": 10
        }

        if market_id:
            params["market"] = market_id

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        trades = response.json()
        print(f"✓ Success! Fetched {len(trades)} trades\n")

        if trades:
            trade = trades[0]
            print("Sample Trade Structure:")
            print(json.dumps(trade, indent=2)[:800] + "...\n")

            # Extract key fields
            print("Key Fields:")
            print(f"  - Transaction Hash: {trade.get('transactionHash', 'N/A')}")
            print(f"  - Trader: {trade.get('trader', 'N/A')}")
            print(f"  - Market: {trade.get('market', 'N/A')}")
            print(f"  - Side: {trade.get('side', 'N/A')}")
            print(f"  - Size: {trade.get('size', 'N/A')}")
            print(f"  - Price: {trade.get('price', 'N/A')}")

        return trades

    except Exception as e:
        print(f"✗ Error: {e}")
        return None


def test_data_holders(market_id):
    """Fetch top holders for a market"""
    print("\n[3] Testing Data API - Holders Endpoint")
    print("=" * 60)

    try:
        url = f"{DATA_API}/holders"
        params = {
            "market": market_id,
            "limit": 10
        }

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        holders = response.json()
        print(f"✓ Success! Fetched {len(holders)} holders\n")

        if holders:
            holder = holders[0]
            print("Sample Holder Structure:")
            print(json.dumps(holder, indent=2)[:500] + "...\n")

            print("Top 5 Holders:")
            for i, h in enumerate(holders[:5], 1):
                print(f"  {i}. {h.get('user', 'N/A')[:10]}... - {h.get('size', 0)} shares")

        return holders

    except Exception as e:
        print(f"✗ Error: {e}")
        return None


def test_gamma_events():
    """Fetch events from Gamma API"""
    print("\n[4] Testing Gamma API - Events Endpoint")
    print("=" * 60)

    try:
        url = f"{GAMMA_API}/events"
        params = {
            "limit": 3,
            "active": True
        }

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        events = response.json()
        print(f"✓ Success! Fetched {len(events)} events\n")

        if events:
            event = events[0]
            print("Sample Event Structure:")
            print(json.dumps(event, indent=2)[:800] + "...\n")

        return events

    except Exception as e:
        print(f"✗ Error: {e}")
        return None


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("ARGUS - Polymarket API Reconnaissance")
    print("Testing API connectivity and data structures")
    print("=" * 60)

    # Test 1: Fetch markets
    markets = test_gamma_markets()

    # Test 2: Fetch trades (general)
    trades = test_data_trades()

    # Test 3: If we have a market, fetch its holders
    if markets and len(markets) > 0:
        market_id = markets[0].get('condition_id')
        if market_id:
            holders = test_data_holders(market_id)

    # Test 4: Fetch events
    events = test_gamma_events()

    print("\n" + "=" * 60)
    print("Reconnaissance Complete!")
    print("=" * 60)
    print("\nNext Steps:")
    print("  1. Review the data structures above")
    print("  2. Design database schema to match")
    print("  3. Build real-time ingestion pipeline")
    print("=" * 60 + "\n")
