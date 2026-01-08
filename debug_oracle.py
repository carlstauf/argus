
import asyncio
import os
import psycopg2
from dotenv import load_dotenv
from src.intelligence.oracle import GeminiOracle

load_dotenv()

async def test_oracle():
    print("--- ARGUS ORACLE DEBUGGER ---")
    
    # 1. Connect DB
    try:
        conn = psycopg2.connect(os.getenv('DATABASE_URL'))
        cursor = conn.cursor()
        print("✓ DB Connected")
    except Exception as e:
        print(f"✗ DB Connection Failed: {e}")
        return

    # 2. Fetch Query
    print("\nFetching top 5 markets...")
    try:
        cursor.execute("""
            SELECT 
                m.condition_id, 
                m.question, 
                (SELECT price FROM trades WHERE condition_id = m.condition_id ORDER BY executed_at DESC LIMIT 1) as price,
                (SELECT SUM(value_usd) FROM trades WHERE condition_id = m.condition_id AND executed_at > NOW() - INTERVAL '24h') as volume_24h
            FROM markets m
            WHERE 
                m.status = 'ACTIVE' 
                AND m.question NOT LIKE '%%vs%%'
                AND m.question NOT LIKE '%%Bitcoin%%'
            ORDER BY volume_24h DESC
            LIMIT 5
        """)
        rows = cursor.fetchall()
        print(f"✓ Found {len(rows)} markets")
        for row in rows:
            print(f"  - {row[1]} (Price: {row[2]}, Vol: {row[3]})")
            
        markets = []
        for row in rows:
            markets.append({
                'condition_id': row[0],
                'question': row[1],
                'price': float(row[2]) if row[2] else 0.5,
                'volume_24h': float(row[3]) if row[3] else 0
            })
            
    except Exception as e:
        print(f"✗ Query Failed: {e}")
        return

    # 3. Test Oracle
    print("\nInitializing Oracle...")
    oracle = GeminiOracle()
    if not oracle.model:
        print("✗ Oracle Init Failed (Check API Key)")
        return
    print(f"✓ Oracle Ready (Model: {oracle.model.model_name})")

    print("\nScanning Markets...")
    results = await oracle.scan_markets(markets)
    
    print(f"\nRESULTS ({len(results)} insights):")
    for res in results:
        print(res)

    print("\nDone.")

if __name__ == "__main__":
    asyncio.run(test_oracle())
