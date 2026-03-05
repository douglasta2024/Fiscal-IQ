import json
import os
import re
from datetime import datetime, timezone
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()


SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_PUBLISHABLE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

EXCLUDE_TICKER_RE = re.compile(r"\.(W|WS|WT|WTS|RT|R|U)$", re.IGNORECASE)

def is_excluded_ticker(ticker: str) -> bool:
    return bool(EXCLUDE_TICKER_RE.search(ticker or ""))

def chunk_list(items, size=1000):
    for i in range(0, len(items), size):
        yield items[i:i + size]

def upload_json_file(json_path: str, table_name: str = "stocks", batch_size: int = 1000):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    now_iso = datetime.now(timezone.utc).isoformat()

    rows = []
    for item in data:
        if not all(k in item for k in ("ticker", "exchange", "name", "asset_type")):
            continue

        ticker = str(item["ticker"]).strip()
        if is_excluded_ticker(ticker):
            continue

        rows.append({
            "ticker": ticker,
            "exchange": str(item["exchange"]).strip(),
            "name": str(item["name"]).strip(),
            "asset_type": str(item["asset_type"]).strip(),
            "price": 0,
            "last_updated": now_iso,
        })

    print(f"Prepared {len(rows)} rows from {json_path}")

    for idx, batch in enumerate(chunk_list(rows, batch_size), start=1):
        try:
            resp = (
                supabase
                .table(table_name)
                .upsert(batch, on_conflict="ticker")
                .execute()
            )
        except Exception as e:
            raise RuntimeError(f"Upload failed (batch {idx}) from {json_path}: {e}") from e

        returned = len(resp.data) if getattr(resp, "data", None) is not None else "unknown"
        print(f"Uploaded batch {idx} ({len(batch)} rows) | returned {returned}")

    print(f"✅ Finished uploading {json_path}\n")

def main():
    upload_json_file("nasdaq.json")
    upload_json_file("nyse.json")

if __name__ == "__main__":
    main()