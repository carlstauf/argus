"""
ARGUS - Polymarket API Client
Handles all communication with Polymarket's APIs
"""

import os
import time
import requests
from typing import Dict, List, Optional, Any, Tuple
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
    
    def check_gamma_api_health(self) -> bool:
        """
        Check Gamma API health status
        Docs: https://docs.polymarket.com/api-reference/gamma-status/gamma-api-health-check
        """
        try:
            response = self.session.get(f"{self.gamma_api}/status", timeout=5)
            return response.status_code == 200 and response.text.strip() == "OK"
        except:
            return False

    # ============================================================
    # GAMMA API - Market Data
    # ============================================================

    def get_markets(
        self,
        limit: int = 100,
        offset: int = 0,
        active: bool = True,
        closed: bool = False,
        order: str = 'id',
        ascending: bool = False,
        tag_id: Optional[int] = None
    ) -> List[Dict]:
        """
        Fetch markets from Gamma API
        Following Polymarket docs: https://docs.polymarket.com/gamma-structure/fetching-markets
        
        Args:
            limit: Number of results (default 100)
            offset: Pagination offset (default 0)
            active: Filter active markets (default True)
            closed: Include closed markets (default False) - set to False for active only
            order: Order field (default 'id')
            ascending: Sort order (default False = newest first)
            tag_id: Filter by tag ID (optional)
        """
        url = f"{self.gamma_api}/markets"
        params = {
            'limit': limit,
            'offset': offset,
            'closed': str(closed).lower()  # Docs recommend closed=false for active markets
        }
        
        if active:
            params['active'] = str(active).lower()
        if order:
            params['order'] = order
        if ascending is not None:
            params['ascending'] = str(ascending).lower()
        if tag_id:
            params['tag_id'] = tag_id

        data = self._make_request(url, params)
        return data if data else []

    def get_market_by_id(self, condition_id: str) -> Optional[Dict]:
        """Get a specific market by condition ID"""
        url = f"{self.gamma_api}/markets/{condition_id}"
        return self._make_request(url)
    
    def get_market_by_slug(self, slug: str) -> Optional[Dict]:
        """
        Get a specific market by slug (recommended method per docs)
        Docs: https://docs.polymarket.com/gamma-structure/fetching-markets#1-fetch-by-slug
        """
        url = f"{self.gamma_api}/markets/slug/{slug}"
        return self._make_request(url)

    def get_events(
        self,
        limit: int = 100,
        offset: int = 0,
        active: bool = True,
        closed: bool = False,
        order: str = 'id',
        ascending: bool = False,
        tag_id: Optional[int] = None
    ) -> List[Dict]:
        """
        Fetch events (groups of markets) from Gamma API
        Following Polymarket docs: https://docs.polymarket.com/gamma-structure/fetching-markets
        Recommended for fetching all active markets efficiently.
        
        Args:
            limit: Number of results (default 100)
            offset: Pagination offset (default 0)
            active: Filter active events (default True)
            closed: Include closed events (default False) - set to False for active only
            order: Order field (default 'id')
            ascending: Sort order (default False = newest first)
            tag_id: Filter by tag ID (optional)
        """
        url = f"{self.gamma_api}/events"
        params = {
            'limit': limit,
            'offset': offset,
            'closed': str(closed).lower()  # Docs recommend closed=false for active markets
        }
        
        if active:
            params['active'] = str(active).lower()
        if order:
            params['order'] = order
        if ascending is not None:
            params['ascending'] = str(ascending).lower()
        if tag_id:
            params['tag_id'] = tag_id

        data = self._make_request(url, params)
        return data if data else []
    
    def get_event_by_slug(self, slug: str) -> Optional[Dict]:
        """
        Get a specific event by slug (recommended method per docs)
        Docs: https://docs.polymarket.com/gamma-structure/fetching-markets#1-fetch-by-slug
        """
        url = f"{self.gamma_api}/events/slug/{slug}"
        return self._make_request(url)

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
        Returns trades sorted by timestamp descending (newest first)

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
        
        if data:
            # Sort by timestamp descending to ensure newest trades first
            data.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
        
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

    def get_wallet_first_trade_timestamp(self, wallet_address: str) -> Optional[int]:
        """
        Get the timestamp of a wallet's FIRST EVER trade on Polymarket
        
        This is critical for accurate "fresh wallet" detection.
        A wallet created last year should NOT be flagged as fresh.
        
        Args:
            wallet_address: The wallet address to check
            
        Returns:
            Unix timestamp of first trade, or None if no trades found
        """
        try:
            # Fetch trades for this user (API returns newest first)
            # We need to get enough to find the oldest one
            trades = self.get_trades(user=wallet_address, limit=500)
            
            if not trades:
                return None
            
            # Find the oldest trade timestamp
            oldest_timestamp = None
            for trade in trades:
                ts = trade.get('timestamp', 0)
                if ts > 0:
                    if oldest_timestamp is None or ts < oldest_timestamp:
                        oldest_timestamp = ts
            
            return oldest_timestamp
            
        except Exception:
            return None

    def is_wallet_truly_fresh(self, wallet_address: str, max_age_hours: float = 72) -> Tuple[bool, float]:
        """
        Check if a wallet is TRULY fresh (first traded recently on Polymarket)
        
        Args:
            wallet_address: The wallet to check
            max_age_hours: Maximum age in hours to be considered "fresh"
            
        Returns:
            Tuple of (is_fresh: bool, age_hours: float)
            age_hours will be -1 if we couldn't determine
        """
        first_trade_ts = self.get_wallet_first_trade_timestamp(wallet_address)
        
        if first_trade_ts is None:
            # No trade history found - could be truly new or API issue
            return (True, 0)  # Assume fresh if no history
        
        # Calculate age
        current_time = time.time()
        age_seconds = current_time - first_trade_ts
        age_hours = age_seconds / 3600
        
        is_fresh = age_hours < max_age_hours
        
        return (is_fresh, age_hours)

    # ============================================================
    # Batch Operations
    # ============================================================

    def get_all_active_markets(self) -> List[Dict]:
        """
        Fetch ALL active markets by paginating through results
        Following Polymarket best practices: use events endpoint for efficiency
        Docs: https://docs.polymarket.com/gamma-structure/fetching-markets#3-fetch-all-active-markets
        """
        all_markets = []
        offset = 0
        batch_size = 100

        while True:
            # Use events endpoint as recommended by docs (more efficient)
            batch = self.get_events(
                limit=batch_size,
                offset=offset,
                active=True,
                closed=False,
                order='id',
                ascending=False  # Newest first
            )

            if not batch:
                break

            # Extract markets from events
            for event in batch:
                markets = event.get('markets', [])
                all_markets.extend(markets)

            offset += batch_size

            # Rate limiting (respect API limits)
            time.sleep(0.1)

            # Safety check
            if offset > 50000:
                print("Warning: Hit safety limit of 50,000 events")
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
