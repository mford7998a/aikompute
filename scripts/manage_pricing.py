#!/usr/bin/env python3
"""
SaaS Pricing Management Tool for AI Inference Gateway.
Allows listing, adding, and updating per-model pricing in the database.
"""

import os
import sys
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Load env from parent dir
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

DB_PASSWORD = os.getenv("DB_PASSWORD", "changeme_in_production")
DB_NAME = "inference_gateway"
DB_USER = "inference"
DB_HOST = "localhost"  # run locally or via docker-compose exec
DB_PORT = "5432"

def get_conn():
    return psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT
    )

def list_pricing():
    conn = get_conn()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT model_pattern, provider_type, input_cost_per_million, output_cost_per_million, priority, is_active
            FROM model_pricing
            ORDER BY priority DESC, created_at DESC
        """)
        rows = cur.fetchall()
        
    print("\n" + "="*80)
    print(f"{'MODEL PATTERN':<25} | {'PROVIDER':<20} | {'IN/1M':<10} | {'OUT/1M':<10} | {'PRIO'}")
    print("-" * 80)
    for row in rows:
        active_str = "" if row['is_active'] else " [INACTIVE]"
        print(f"{row['model_pattern'] + active_str:<25} | {str(row['provider_type']):<20} | ${row['input_cost_per_million']/1_000_000:<9.2f} | ${row['output_cost_per_million']/1_000_000:<9.2f} | {row['priority']}")
    print("="*80 + "\n")
    conn.close()

def set_pricing(pattern, provider, in_cost, out_cost, priority=10):
    """
    Sets pricing for a model.
    in_cost/out_cost are in actual dollars per million tokens (e.g. 0.5 for 50 cents)
    """
    in_micro = int(float(in_cost) * 1_000_000)
    out_micro = int(float(out_cost) * 1_000_000)
    
    conn = get_conn()
    with conn.cursor() as cur:
        # Check if already exists for this exact pattern + provider
        cur.execute("""
            SELECT id FROM model_pricing 
            WHERE model_pattern = %s AND (provider_type = %s OR (provider_type IS NULL AND %s IS NULL))
        """, (pattern, provider, provider))
        existing = cur.fetchone()
        
        if existing:
            cur.execute("""
                UPDATE model_pricing 
                SET input_cost_per_million = %s, output_cost_per_million = %s, priority = %s, is_active = true
                WHERE id = %s
            """, (in_micro, out_micro, priority, existing[0]))
            print(f"Updated pricing for {pattern} ({provider or 'any-provider'})")
        else:
            cur.execute("""
                INSERT INTO model_pricing (model_pattern, provider_type, input_cost_per_million, output_cost_per_million, priority)
                VALUES (%s, %s, %s, %s, %s)
            """, (pattern, provider, in_micro, out_micro, priority))
            print(f"Created new pricing for {pattern} ({provider or 'any-provider'})")
            
    conn.commit()
    conn.close()

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python manage_pricing.py list")
        print("  python manage_pricing.py set <pattern> <provider|any> <in_usd_per_1M> <out_usd_per_1M> [priority]")
        sys.stdout.flush()
        return

    cmd = sys.argv[1].lower()
    if cmd == "list":
        list_pricing()
    elif cmd == "set" and len(sys.argv) >= 5:
        pattern = sys.argv[2]
        provider = sys.argv[3] if sys.argv[3].lower() != "any" else None
        in_cost = sys.argv[4]
        out_cost = sys.argv[5]
        prio = int(sys.argv[6]) if len(sys.argv) > 6 else 10
        set_pricing(pattern, provider, in_cost, out_cost, prio)
        list_pricing()
    else:
        print("Invalid command or missing arguments.")

if __name__ == "__main__":
    main()
