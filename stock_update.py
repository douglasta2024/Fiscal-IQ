### OLD FILES ###

import os
import pandas as pd
import asyncio
from supabase import create_client, Client
from datetime import datetime, timezone
from stock_scrapper import scrape_quotes
from dotenv import load_dotenv

load_dotenv()

DB_URL = os.getenv("SUPABASE_URL") 
PUBLIC_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY")
supabase: Client = create_client(DB_URL, PUBLIC_KEY)

nasdaq = pd.read_json("JSON/nasdaq.json")
nyse = pd.read_json("JSON/nyse.json")
df = pd.concat([nasdaq, nyse], axis=0)

def chunk_list(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]


async def scrape_in_batches(df, batch_size=5, concurrency=6, headless=True):
    symbols = list(zip(df["ticker"], df["exchange"]))
    all_rows = []  # will hold dicts for supabase upsert

    for i in range(0, len(symbols), batch_size):
        batch = symbols[i: i + batch_size]
        print(f"Processing batch {i // batch_size + 1} with {len(batch)} symbols...")

        data = await scrape_quotes(batch, concurrency=concurrency, headless=headless)

        # don't block the event loop
        await asyncio.sleep(5)

        now_iso = datetime.now(timezone.utc).isoformat()

        for row in data:
            if "error" in row:
                print(row.get("ticker"), "ERROR:", row["error"])
                continue

            ticker = row.get("ticker")
            exchange = row.get("exchange")  # must exist (or map it yourself)
            price = row.get("price")        # numeric

            if ticker and exchange and price is not None:
                all_rows.append({
                    "ticker": ticker,
                    "exchange": exchange,
                    "price": price,
                    "last_updated": now_iso
                })
                print(ticker, exchange, row.get("price_text"), price)
        break

    if not all_rows:
        print("No rows to update.")
        return

    # Upsert in chunks (prevents huge HTTP payloads)
    # Tune chunk size based on your row size; 200-1000 is typical.
    CHUNK_SIZE = 500

    total = 0
    for chunk in chunk_list(all_rows, CHUNK_SIZE):
        resp = supabase.table("stocks").upsert(
            chunk,
            on_conflict="ticker,exchange"
        ).execute()

        # Basic safety check:
        # Depending on supabase-py version, errors surface differently; this at least prints any server errors.
        if getattr(resp, "error", None):
            raise RuntimeError(f"Supabase upsert error: {resp.error}")

        total += len(chunk)

    print(f"Upserted/updated {total} rows.")

if __name__ == "__main__":
    asyncio.run(scrape_in_batches(df, batch_size=5, concurrency=6, headless=True))