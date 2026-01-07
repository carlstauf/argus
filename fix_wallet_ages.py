#!/usr/bin/env python3
"""
Fix Wallet Ages - Backfill first_seen_at from earliest trades
This ensures wallet freshness is based on ACTUAL first trade, not when we started tracking
"""

import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def fix_wallet_ages():
    """Backfill wallet first_seen_at from earliest trades"""
    conn = psycopg2.connect(os.getenv('DATABASE_URL'))
    cursor = conn.cursor()
    
    print("🔧 Fixing wallet ages...")
    
    # Update all wallets to use earliest trade timestamp
    cursor.execute("""
        UPDATE wallets w
        SET first_seen_at = (
            SELECT MIN(executed_at)
            FROM trades t
            WHERE t.wallet_address = w.address
        )
        WHERE EXISTS (
            SELECT 1 FROM trades t WHERE t.wallet_address = w.address
        )
        AND (
            SELECT MIN(executed_at)
            FROM trades t
            WHERE t.wallet_address = w.address
        ) < w.first_seen_at
    """)
    
    updated = cursor.rowcount
    conn.commit()
    
    print(f"✓ Updated {updated} wallets")
    
    # Verify
    cursor.execute("""
        SELECT COUNT(*)
        FROM wallets w
        WHERE EXISTS (
            SELECT 1 FROM trades t WHERE t.wallet_address = w.address
        )
        AND w.first_seen_at != (
            SELECT MIN(executed_at)
            FROM trades t
            WHERE t.wallet_address = w.address
        )
    """)
    
    mismatches = cursor.fetchone()[0]
    
    if mismatches == 0:
        print("✓ All wallet ages are correct!")
    else:
        print(f"⚠️  {mismatches} wallets still have mismatched ages")
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    fix_wallet_ages()

