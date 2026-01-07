
import os
import asyncio
import logging
from typing import List, Dict, Optional
import google.generativeai as genai
from datetime import datetime

logger = logging.getLogger(__name__)

class GeminiOracle:
    """
    The Oracle: Uses Gemini Flash 1.5 to analyze prediction markets
    and identify "obvious" mispriced bets where reality diverges from market probability.
    """

    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.warning("GEMINI_API_KEY not found. Oracle will be disabled.")
            self.model = None
            return

        try:
            genai.configure(api_key=api_key)
            # Use Gemini 3.0 Flash (Preview) as requested
            self.model = genai.GenerativeModel('gemini-3-flash-preview')
            logger.info("Gemini Oracle initialized (Model: gemini-3-flash-preview)")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini Oracle: {e}")
            self.model = None

        # Cache content to avoid re-analyzing same market too often
        # Key: condition_id, Value: (timestamp, analysis_result)
        self.cache = {}
        self.cache_ttl_hours = 4

    async def scan_markets(self, markets: List[Dict]) -> List[Dict]:
        """
        Scan a batch of markets and return those with 'obvious' mispricing.
        Ranked by confidence/divergence.
        """
        if not self.model:
            return []

        candidates = []
        
        # Filter strictly for HIGH conviction/volume markets first 
        # to avoid wasting tokens on junk
        valid_markets = [
            m for m in markets 
            if m.get('volume_24h', 0) > 1000  # Must have some liquidty
            and m.get('question')
        ]

        # Analyze in batches or individually? 
        # Flash is fast, let's try individual for now but concurrent
        chunk_size = 5
        results = []
        
        for i in range(0, len(valid_markets), chunk_size):
            batch = valid_markets[i:i+chunk_size]
            batch_tasks = [self._analyze_single_market(m) for m in batch]
            batch_results = await asyncio.gather(*batch_tasks)
            results.extend([r for r in batch_results if r])
            
        # Sort by confidence/discrepancy
        results.sort(key=lambda x: x['confidence'], reverse=True)
        return results

    async def _analyze_single_market(self, market: Dict) -> Optional[Dict]:
        """
        Analyze a single market for obvious mispricing via Gemini
        """
        condition_id = market.get('condition_id')
        
        # Check cache
        if condition_id in self.cache:
            ts, result = self.cache[condition_id]
            if (datetime.now() - ts).total_seconds() < self.cache_ttl_hours * 3600:
                return result

        question = market.get('question')
        price = market.get('price', 0.5)
        implied_prob = price * 100
        
        # PROMPT ENGINEERING
        # Strict instructions to find OBVIOUS reality gaps only
        prompt = f"""
        You are a superintelligence analyzing a prediction market for mispricing.
        
        MARKET: "{question}"
        CURRENT ODDS: {implied_prob:.1f}% chance of happening (YES).
        
        TASK: Is this market OBVIOUSLY mispriced based on current real-world reality/news?
        
        CRITERIA:
        - Identify ONLY "obvious" discrepancies (e.g., event already happened, or is impossible, or odds are wildly off from polls/consensus).
        - Ignore "gambling" or "50/50" uncertain events (crypto prices, sports games unless match is fixed/done).
        - Focus on Politics, World Events, Tech, Business.
        
        RESPONSE FORMAT (JSON):
        {{
            "is_mispriced": boolean,
            "verdict": "UNDERVALUED" or "OVERVALUED" or "FAIR",
            "estimated_real_odds": number (0-100),
            "confidence": number (0-100) (How sure are you?),
            "reasoning": "Brief 1-sentence explanation why."
        }}
        
        Respond with valid JSON only.
        """
        
        try:
            # Run in thread executor to avoid blocking regular loop
            response = await asyncio.to_thread(
                self.model.generate_content, 
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            
            import json
            data = json.loads(response.text)
            
            # Filter for high-confidence mispricing only
            if data.get('is_mispriced') and data.get('confidence') > 75:
                # Add market context
                data['question'] = question
                data['market_price'] = price
                data['condition_id'] = condition_id
                
                # Update cache
                self.cache[condition_id] = (datetime.now(), data)
                return data
                
            # Cache negative results too (Fair bets)
            self.cache[condition_id] = (datetime.now(), None)
            return None
            
        except Exception as e:
            logger.error(f"Oracle analysis failed for {question}: {e}")
            return None
