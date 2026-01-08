"""
ARGUS - Gemini Oracle
Triple-checks Polymarket for obvious mispriced bets.
"""

import os
import asyncio
import json
import logging
import requests
from datetime import datetime
from typing import List, Dict, Optional

import warnings
warnings.filterwarnings("ignore")

import google.generativeai as genai

logger = logging.getLogger(__name__)


class GeminiOracle:
    """
    The Oracle: Scrapes Polymarket + uses Gemini 3 Flash to find mispriced bets.
    Triple-checks every analysis.
    """

    POLYMARKET_API = "https://gamma-api.polymarket.com"

    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.warning("GEMINI_API_KEY not found. Oracle disabled.")
            self.model = None
            return

        try:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel('gemini-3-flash-preview')
            print("[ORACLE] ✓ Gemini 3 Flash initialized")
        except Exception as e:
            logger.error(f"Failed to init Oracle: {e}")
            self.model = None

        self.cache: Dict[str, tuple] = {}
        self.cache_ttl_hours = 1

    def scrape_polymarket_markets(self, limit: int = 50) -> List[Dict]:
        """Scrape live markets from Polymarket API."""
        try:
            url = f"{self.POLYMARKET_API}/markets"
            params = {"limit": limit, "active": "true", "closed": "false"}
            
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            markets = resp.json()
            
            formatted = []
            for m in markets:
                question = m.get('question', '')
                slug = m.get('slug', '')
                
                # Skip crypto gambling
                skip = ['bitcoin', 'ethereum', 'xrp', 'crypto', 'up or down', 'solana']
                if any(kw.lower() in question.lower() for kw in skip):
                    continue
                
                # Parse price
                outcomes = m.get('outcomePrices', [])
                price = 0.5
                try:
                    if isinstance(outcomes, str):
                        outcomes = json.loads(outcomes)
                    if outcomes:
                        price = float(outcomes[0])
                except:
                    pass
                
                link = f"https://polymarket.com/event/{slug}" if slug else ""
                
                formatted.append({
                    'condition_id': m.get('conditionId'),
                    'question': question,
                    'slug': slug,
                    'price': price,
                    'volume': float(m.get('volume', 0)),
                    'link': link
                })
            
            formatted.sort(key=lambda x: x['volume'], reverse=True)
            print(f"[ORACLE] Scraped {len(formatted)} markets")
            return formatted[:20]
            
        except Exception as e:
            logger.error(f"Scrape failed: {e}")
            return []

    async def scan_markets(self, markets: List[Dict] = None) -> List[Dict]:
        """Scan markets for mispricing with triple-check."""
        if not self.model:
            return []

        if not markets:
            markets = self.scrape_polymarket_markets()
        
        if not markets:
            return []

        print(f"[ORACLE] Analyzing {len(markets)} markets...")
        
        results = []
        for m in markets:
            r = await self._analyze_market(m)
            if r:
                results.append(r)
        
        results.sort(key=lambda x: x.get('confidence', 0), reverse=True)
        print(f"[ORACLE] Found {len(results)} trades")
        return results

    async def _analyze_market(self, market: Dict) -> Optional[Dict]:
        """Triple-check analysis of a single market."""
        cid = market.get('condition_id')
        question = market.get('question', '')
        link = market.get('link', '')
        
        # Check cache
        if cid in self.cache:
            ts, res = self.cache[cid]
            if (datetime.now() - ts).seconds < self.cache_ttl_hours * 3600:
                return res

        price = market.get('price', 0.5)
        pct = price * 100
        
        prompt = f"""You are a prediction market analyst. TRIPLE-CHECK this bet.

MARKET: "{question}"
YES PRICE: {pct:.1f}%
LINK: {link}

STEP 1: What do facts/news say about true probability?
STEP 2: What could be wrong with Step 1?
STEP 3: Final verdict after considering Step 2.

RESPOND JSON:
{{
    "is_mispriced": true/false,
    "action": "BUY YES" or "BUY NO" or "NO TRADE",
    "estimated_real_odds": 0-100,
    "confidence": 0-100,
    "edge_percent": number,
    "reasoning": "1 sentence"
}}

RULES:
- Only trades with >15% edge
- BUY YES = market undervalues YES
- BUY NO = market overvalues YES
- NO TRADE if uncertain
- JSON only"""

        try:
            resp = await asyncio.to_thread(
                self.model.generate_content,
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            
            data = json.loads(resp.text.strip())
            
            if data.get('is_mispriced') and data.get('action') in ['BUY YES', 'BUY NO'] and data.get('confidence', 0) >= 70:
                data['question'] = question
                data['market_price'] = price
                data['condition_id'] = cid
                data['link'] = link
                
                self.cache[cid] = (datetime.now(), data)
                return data
            
            self.cache[cid] = (datetime.now(), None)
            return None
            
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            return None


if __name__ == "__main__":
    async def test():
        from dotenv import load_dotenv
        load_dotenv()
        
        print("\n=== ORACLE TEST ===\n")
        oracle = GeminiOracle()
        
        if not oracle.model:
            print("FAILED: Check GEMINI_API_KEY")
            return
        
        results = await oracle.scan_markets()
        
        print(f"\n=== TRADES ({len(results)}) ===\n")
        for r in results:
            act = r.get('action', '?')
            emoji = "🟢" if act == "BUY YES" else "🔴" if act == "BUY NO" else "⚪"
            print(f"{emoji} [{act}] {r['question']}")
            print(f"   Mkt: {r['market_price']*100:.0f}% | Real: {r['estimated_real_odds']}% | Edge: {r.get('edge_percent', 0)}%")
            print(f"   {r['reasoning']}")
            print(f"   🔗 {r['link']}\n")
    
    asyncio.run(test())