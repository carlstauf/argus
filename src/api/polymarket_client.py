"""
ARGUS - Polymarket API Client
Handles all communication with Polymarket's APIs
"""

import os
import time
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()


class PolymarketClient:
    """Client for interacting with Polymarket APIs"""

    def __init__(self):
        self.gamma_api = os.getenv('GAMMA_API_URL', 'https://gamma-api.polymarket.com')
        self.data_api = os.getenv('DATA_API_URL', 'https://data-api.polymarket.com')
        self.clob_api = os.getenv('CLOB_API_URL', 'https://clob.polymarket.com')

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'ARGUS/1.0'
        })

    def _make_request(self, url: str, params: Optional[Dict] = None) -> Any:
        """Make a GET request with error handling"""
        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error making request to {url}: {e}")
            return None

    # ============================================================
    # GAMMA API - Market Data
    # ============================================================

    def get_markets(
        self,
        limit: int = 100,
        offset: int = 0,
        active: bool = True,
        closed: bool = False
    ) -> List[Dict]:
        """
        Fetch markets from Gamma API
        """
        url = f"{self.gamma_api}/markets"
        params = {
            'limit': limit,
            'offset': offset,
            'active': active,
            'closed': closed
        }

        data = self._make_request(url, params)
        return data if data else []

    def get_market_by_id(self, condition_id: str) -> Optional[Dict]:
        """Get a specific market by condition ID"""
        url = f"{self.gamma_api}/markets/{condition_id}"
        return self._make_request(url)

    def get_events(
        self,
        limit: int = 100,
        offset: int = 0,
        active: bool = True
    ) -> List[Dict]:
        """
        Fetch events (groups of markets) from Gamma API
        """
        url = f"{self.gamma_api}/events"
        params = {
            'limit': limit,
            'offset': offset,
            'active': active
        }

        data = self._make_request(url, params)
        return data if data else []

    # ============================================================
    # DATA API - Trades & Positions
    # ============================================================

    def get_trades(
        self,
        market: Optional[str] = None,
        user: Optional[str] = None,
        side: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        Fetch trades from Data API

        Args:
            market: Condition ID to filter by
            user: Wallet address to filter by
            side: 'BUY' or 'SELL'
            limit: Max results (max 500)
        """
        url = f"{self.data_api}/trades"
        params = {'limit': min(limit, 500)}

        if market:
            params['market'] = market
        if user:
            params['user'] = user
        if side:
            params['side'] = side

        data = self._make_request(url, params)
        return data if data else []

    def get_positions(
        self,
        user: str,
        market: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        Fetch positions for a user

        Args:
            user: Wallet address (required)
            market: Condition ID to filter by
            limit: Max results (max 500)
        """
        url = f"{self.data_api}/positions"
        params = {
            'user': user,
            'limit': min(limit, 500)
        }

        if market:
            params['market'] = market

        data = self._make_request(url, params)
        return data if data else []

    def get_holders(
        self,
        market: str,
        limit: int = 100
    ) -> List[Dict]:
        """
        Get top holders for a market

        Args:
            market: Condition ID (required)
            limit: Max results (max 100)
        """
        url = f"{self.data_api}/holders"
        params = {
            'market': market,
            'limit': min(limit, 100)
        }

        data = self._make_request(url, params)
        return data if data else []

    def get_user_value(
        self,
        user: str,
        market: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Get total USD value of a user's positions

        Args:
            user: Wallet address (required)
            market: Optional condition ID
        """
        url = f"{self.data_api}/value"
        params = {'user': user}

        if market:
            params['market'] = market

        return self._make_request(url, params)

    # ============================================================
    # Batch Operations
    # ============================================================

    def get_all_active_markets(self) -> List[Dict]:
        """
        Fetch ALL active markets by paginating through results
        """
        all_markets = []
        offset = 0
        batch_size = 100

        while True:
            batch = self.get_markets(limit=batch_size, offset=offset, active=True)

            if not batch:
                break

            all_markets.extend(batch)
            offset += batch_size

            # Rate limiting
            time.sleep(0.1)

            # Safety check (increased to 50k)
            if offset > 50000:
                print("Warning: Hit safety limit of 50,000 markets")
                break

        return all_markets

    def get_recent_trades_stream(
        self,
        interval_seconds: int = 10,
        limit_per_batch: int = 100
    ):
        """
        Generator that yields batches of recent trades
        Use this for real-time monitoring

        Usage:
            for trades in client.get_recent_trades_stream():
                process_trades(trades)
        """
        last_timestamp = None

        while True:
            trades = self.get_trades(limit=limit_per_batch)

            if trades:
                # Filter out trades we've already seen
                if last_timestamp:
                    new_trades = [
                        t for t in trades
                        if t.get('timestamp', 0) > last_timestamp
                    ]
                else:
                    new_trades = trades

                if new_trades:
                    yield new_trades
                    last_timestamp = max(t.get('timestamp', 0) for t in new_trades)

            time.sleep(interval_seconds)

    # ============================================================
    # Utility Methods
    # ============================================================

    @staticmethod
    def parse_timestamp(unix_timestamp: int) -> datetime:
        """Convert Unix timestamp to datetime"""
        return datetime.fromtimestamp(unix_timestamp)

    @staticmethod
    def calculate_trade_value(size: float, price: float) -> float:
        """Calculate USD value of a trade"""
        return size * price


if __name__ == "__main__":
    # Quick test
    print("Testing Polymarket Client...")
    client = PolymarketClient()

    print("\n1. Fetching 5 markets...")
    markets = client.get_markets(limit=5)
    print(f"   Found {len(markets)} markets")

    if markets:
        market_id = markets[0].get('conditionId')
        if market_id:
            print(f"\n2. Fetching holders for market: {market_id[:10]}...")
            holders = client.get_holders(market_id, limit=5)
            print(f"   Found {len(holders)} holders")

    print("\n3. Fetching recent trades...")
    trades = client.get_trades(limit=5)
    print(f"   Found {len(trades)} trades")

    print("\n✓ Client test complete!")
