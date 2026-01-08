"""
ARGUS - Gemini Oracle
The All-Seeing Eye: Scrapes Polymarket and uses Gemini 3 Flash to find obvious mispriced bets.
"""

import os
import asyncio
import logging
import json
import requests
from typing import List, Dict, Optional
from datetime import datetime

# Use warnings to track deprecation notices
import warnings
warnings.filterwarnings("ignore")

import google.generativeai as genai

logger = logging.getLogger(__name__)


class GeminiOracle:
    """
    The Oracle: Directly scrapes Polymarket and uses Gemini 3 Flash
    to identify 'obvious' mispriced bets where reality diverges from market probability.
    """

    POLYMARKET_API = "https://gamma-api.polymarket.com"

    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.warning("GEMINI_API_KEY not found. Oracle will be disabled.")
            self.model = None
            return

        try:
            genai.configure(api_key=api_key)
            # Use Gemini 3.0 Flash (Preview)
            self.model = genai.GenerativeModel('gemini-3-flash-preview')
            print("[ORACLE] ✓ Gemini 3 Flash initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini Oracle: {e}")
            self.model = None

        # Cache to avoid re-analyzing same market too often
        self.cache: Dict[str, tuple] = {}
        self.cache_ttl_hours = 1  # Short TTL for freshness

    def scrape_polymarket_markets(self, limit: int = 50) -> List[Dict]:
        """
        Scrape live market data directly from Polymarket API.
        Returns top markets by volume with current prices.
        """
        try:
            # Get active markets sorted by volume
            url = f"{self.POLYMARKET_API}/markets"
            params = {
                "limit": limit,
                "active": "true",
                "closed": "false"
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            markets = response.json()
            
            # Filter and format markets
            formatted = []
            for m in markets:
                question = m.get('question', '')
                
                # Skip crypto/sports gambling
                skip_keywords = ['bitcoin', 'ethereum', 'xrp', 'crypto', 'vs.', 'o/u', 'spread', 'up or down']
                if any(kw.lower() in question.lower() for kw in skip_keywords):
                    continue
                
                # Get current price (YES outcome)
                outcomes = m.get('outcomePrices', [])
                price = 0.5
                if outcomes and len(outcomes) > 0:
                    try:
                        price = float(outcomes[0])
                    except:
                        price = 0.5
                
                formatted.append({
                    'condition_id': m.get('conditionId'),
                    'question': question,
                    'price': price,
                    'volume': float(m.get('volume', 0)),
                    'liquidity': float(m.get('liquidity', 0)),
                    'end_date': m.get('endDate')
                })
            
            # Sort by volume descending
            formatted.sort(key=lambda x: x['volume'], reverse=True)
            print(f"[ORACLE] Scraped {len(formatted)} markets from Polymarket")
            return formatted[:20]  # Top 20 by volume
            
        except Exception as e:
            logger.error(f"Failed to scrape Polymarket: {e}")
            print(f"[ORACLE] ✗ Scrape failed: {e}")
            return []

    async def scan_markets(self, markets: List[Dict] = None) -> List[Dict]:
        """
        Scan markets for obvious mispricing.
        If no markets provided, scrapes Polymarket directly.
        """
        if not self.model:
            print("[ORACLE] ✗ Model not initialized")
            return []

        # Scrape fresh data if not provided
        if not markets:
            markets = self.scrape_polymarket_markets()
        
        if not markets:
            print("[ORACLE] No markets to analyze")
            return []

        print(f"[ORACLE] Analyzing {len(markets)} markets with Gemini 3 Flash...")
        
        # Analyze concurrently in small batches
        results = []
        batch_size = 5
        
        for i in range(0, len(markets), batch_size):
            batch = markets[i:i+batch_size]
            batch_tasks = [self._analyze_single_market(m) for m in batch]
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            
            for r in batch_results:
                if r and not isinstance(r, Exception):
                    results.append(r)
        
        # Sort by confidence
        results.sort(key=lambda x: x.get('confidence', 0), reverse=True)
        print(f"[ORACLE] Found {len(results)} mispriced opportunities")
        return results

    async def _analyze_single_market(self, market: Dict) -> Optional[Dict]:
        """
        Analyze a single market for obvious mispricing via Gemini.
        """
        condition_id = market.get('condition_id')
        question = market.get('question', 'Unknown')
        
        # Check cache
        if condition_id in self.cache:
            ts, result = self.cache[condition_id]
            if (datetime.now() - ts).total_seconds() < self.cache_ttl_hours * 3600:
                return result

        price = market.get('price', 0.5)
        implied_prob = price * 100
        
        # PROMPT: Find obvious mispricing
        prompt = f"""You are an expert prediction market analyst. Analyze this bet:

MARKET: "{question}"
CURRENT PRICE: {implied_prob:.1f}% chance of YES

TASK: Is this market OBVIOUSLY mispriced based on public information?

RESPOND IN JSON:
{{
    "is_mispriced": true/false,
    "verdict": "UNDERVALUED" or "OVERVALUED" or "FAIR",
    "estimated_real_odds": number 0-100,
    "confidence": number 0-100,
    "reasoning": "1 sentence why"
}}

RULES:
- Only flag OBVIOUS mispricing (>20% divergence from reality)
- Use current news/polls/facts
- Say FAIR if uncertain
- JSON only, no markdown"""

        try:
            response = await asyncio.to_thread(
                self.model.generate_content,
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            
            # Parse response
            text = response.text.strip()
            data = json.loads(text)
            
            # Only return if mispriced with high confidence
            if data.get('is_mispriced') and data.get('confidence', 0) >= 60:
                data['question'] = question
                data['market_price'] = price
                data['condition_id'] = condition_id
                
                self.cache[condition_id] = (datetime.now(), data)
                return data
            
            # Cache FAIR results
            self.cache[condition_id] = (datetime.now(), None)
            return None
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error for {question}: {e}")
            return None
        except Exception as e:
            logger.error(f"Oracle analysis failed for {question}: {e}")
            return None


# Standalone test
if __name__ == "__main__":
    async def test():
        from dotenv import load_dotenv
        load_dotenv()
        
        print("\n=== ORACLE TEST ===\n")
        oracle = GeminiOracle()
        
        if not oracle.model:
            print("FAILED: Model not initialized. Check GEMINI_API_KEY.")
            return
        
        results = await oracle.scan_markets()
        
        print(f"\n=== RESULTS ({len(results)}) ===\n")
        for r in results:
            print(f"[{r['verdict']}] {r['question']}")
            print(f"  Market: {r['market_price']*100:.1f}% | Real: {r['estimated_real_odds']}% | Conf: {r['confidence']}%")
            print(f"  Reason: {r['reasoning']}\n")
    
    asyncio.run(test())
