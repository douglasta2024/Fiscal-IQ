import asyncio
import re
import os
import time
from typing import Dict, Optional, List, Tuple
from datetime import datetime, timezone
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import pandas as pd
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv() 

DB_URL = os.getenv("SUPABASE_URL") 
PUBLIC_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY")
supabase: Client = create_client(DB_URL, PUBLIC_KEY)

class Database:
    # creates new user into database along with custom portfolio
    @staticmethod
    def create_new_user(email, password, custom_portfolio_name):
        response = supabase.auth.sign_up({
            "email": email,
            "password": password,
            "options": {
                "data": {
                    "portfolio_name": custom_portfolio_name
                }
            }
        })

        if response.user:
            print(f"User sucessfully create! Portfolio {custom_portfolio_name} has been automatically generated.")
        else:
            print("Signup failed...")

    # deletes a user and related data
    @staticmethod
    def delete_user(email, password):
        auth_res = supabase.auth.sign_in_with_password({"email": email, "password": password})

        if not auth_res.user:
            print("Login failed. Check credentials.")
            return False

        service_role_key = os.getenv("SUPABASE_SERVICE_KEY")
        if not service_role_key:
            print("SUPABASE_SERVICE_KEY not found. Cannot delete auth user.")
            return False

        try:
            admin_client: Client = create_client(DB_URL, service_role_key)
            admin_client.auth.admin.delete_user(auth_res.user.id)
            print(f"Deleted auth user: {auth_res.user.email}")
            return True
        except Exception as e:
            print(f"Failed to delete auth user: {e}")
            return False

    # creates another portfolio associated with user
    @staticmethod
    def create_additional_portfolio(email, password, new_portfolio_name):
        # 1. Login to get the user's session
        auth_res = supabase.auth.sign_in_with_password({"email": email, "password": password})

        if auth_res.user:
            user_id = auth_res.user.id
            print(f"Logged in as {auth_res.user.email}")

            # 2. Insert the new portfolio
            # We must provide the user_id so the RLS policy validates the request
            new_portfolio = {
                "user_id": user_id,
                "portfolio_name": new_portfolio_name
            }

            try:
                res = supabase.table("portfolios").insert(new_portfolio).execute()

                if res.data:
                    print(f"✅ Successfully created portfolio: '{new_portfolio_name}'")
                    print(f"Portfolio ID: {res.data[0]['portfolio_id']}")
                    return res.data[0]['portfolio_id']

            except Exception as e:
                print(f"❌ Failed to create portfolio: {e}")
        else:
            print("❌ Login failed. Check credentials.")

    # deletes a portfolio associated with a user
    @staticmethod
    def delete_portfolio(email, password, portfolio_name=None, portfolio_id=None):
        auth_res = supabase.auth.sign_in_with_password({"email": email, "password": password})

        if not auth_res.user:
            print("Login failed. Check credentials.")
            return False

        user_id = auth_res.user.id

        if not portfolio_name and not portfolio_id:
            print("Please provide portfolio_name or portfolio_id.")
            return False

        query = supabase.table("portfolios").select("portfolio_id", "portfolio_name").eq("user_id", user_id)

        if portfolio_id:
            query = query.eq("portfolio_id", portfolio_id)
        else:
            query = query.eq("portfolio_name", portfolio_name)

        try:
            found = query.execute()
            if not found.data:
                print("No matching portfolio found for this user.")
                return False

            target = found.data[0]
            supabase.table("portfolios").delete().eq("portfolio_id", target["portfolio_id"]).eq("user_id", user_id).execute()
            print(f"Deleted portfolio '{target['portfolio_name']}' (ID: {target['portfolio_id']}).")
            return True
        except Exception as e:
            print(f"Failed to delete portfolio: {e}")
            return False

    # retrieves all portfolios associated with a user
    @staticmethod
    def get_user_portfolios(email, password):
        auth_res = supabase.auth.sign_in_with_password({"email": email, "password": password})

        if auth_res.user:
            print(f"Logged in as {auth_res.user.email}")

            try:
                res = supabase.table("portfolios").select("*").eq("user_id", auth_res.user.id).execute()

                if res.data:
                    print(f"Found {len(res.data)} portfolio(s):")
                    for p in res.data:
                        print(f"  - {p['portfolio_name']} (ID: {p['portfolio_id']})")
                    return res.data
                else:
                    print("No portfolios found for this user.")
                    return []

            except Exception as e:
                print(f"Failed to retrieve portfolios: {e}")
                return []
        else:
            print("Login failed. Check credentials.")
            return []

    # adds in stock trade for specific portfolio
    @staticmethod
    def test_add_stock(email, password, symbol, qty, portfolio_name=None):
        # 1. Login
        user_auth = supabase.auth.sign_in_with_password({"email": email, "password": password})

        if user_auth.user:
            print(f"Successfully logged in as {user_auth.user.email}")

            # 2. Logic to find the correct Portfolio ID
            query = supabase.table("portfolios").select("portfolio_id", "portfolio_name", "user_id")

            # If user specified a name, try to find that one specifically
            if portfolio_name:
                query = query.eq("portfolio_name", portfolio_name)

            res = query.execute()

            if res.data:
                # If a match was found (or if we didn't filter, it takes the first one)
                p_id = res.data[0]['portfolio_id']
                actual_name = res.data[0]['portfolio_name']
                u_id = res.data[0]['user_id']
                print(f"Targeting portfolio: '{actual_name}' (ID: {p_id})")

                # 3. Add stock to holdings table
                stock_data = {
                    "user_id" : u_id,
                    "portfolio_id" : p_id,
                    "symbol" : symbol,
                    "quantity" : qty,
                    "average_price" : 150 # placeholder
                }

                insert_res = supabase.table("holdings").insert(stock_data).execute()
                print("Successfully added stock: ", insert_res.data)
            else:
                print(f"Error: No portfolio found matching '{portfolio_name}'")
        else:
            print("Login failed")

    # deletes a stock holding by holding_id
    @staticmethod
    def delete_stock_by_holding_id(email, password, holding_id):
        auth_res = supabase.auth.sign_in_with_password({"email": email, "password": password})

        if not auth_res.user:
            print("Login failed. Check credentials.")
            return False

        user_id = auth_res.user.id

        try:
            # Optional pre-check for clearer message
            existing = (
                supabase.table("holdings")
                .select("holdings_id, symbol, portfolio_id")
                .eq("holdings_id", holding_id)
                .eq("user_id", user_id)
                .execute()
            )

            if not existing.data:
                print("No matching holding found for this user.")
                return False

            delete_res = (
                supabase.table("holdings")
                .delete()
                .eq("holdings_id", holding_id)
                .eq("user_id", user_id)
                .execute()
            )

            if delete_res.data:
                print(f"Deleted holdings_id={holding_id}.")
                return True

            print("Delete request completed, but no row returned.")
            return False

        except Exception as e:
            print(f"Failed to delete holding: {e}")
            return False


class StockScrapper:
    GOOGLE_FINANCE_QUOTE_URL = "https://www.google.com/finance/quote/{ticker}:{exchange}"

    # Resource types to block for speed
    BLOCK_RESOURCE_TYPES = {"image", "media", "font"}
    # Optional: block common analytics/ad endpoints too
    BLOCK_URL_SUBSTRINGS = (
        "google-analytics.com",
        "doubleclick.net",
        "googletagmanager.com",
        "adservice.google.com",
    )

    nasdaq = pd.read_json("JSON/nasdaq.json")
    nyse = pd.read_json("JSON/nyse.json")
    df = pd.concat([nasdaq, nyse], axis=0)    

    @staticmethod
    def _clean_number(text: str) -> Optional[float]:
        if not text:
            return None
        s = re.sub(r"[^0-9,.\-]", "", text).replace(",", "")
        try:
            return float(s)
        except ValueError:
            return None

    @staticmethod
    async def _route_blocker(route):
        req = route.request
        url = req.url
        if req.resource_type in StockScrapper.BLOCK_RESOURCE_TYPES:
            await route.abort()
            return
        if any(x in url for x in StockScrapper.BLOCK_URL_SUBSTRINGS):
            await route.abort()
            return
        await route.continue_()

    @staticmethod
    async def fetch_quote(page, ticker: str, exchange: str = "NASDAQ") -> Dict[str, object]:
        """Fetch a single quote quickly using an existing Page."""
        url = StockScrapper.GOOGLE_FINANCE_QUOTE_URL.format(
            ticker=ticker.upper(), exchange=exchange.upper()
        )

        # DOMContentLoaded is usually enough; full "load" can be much slower.
        await page.goto(url, wait_until="domcontentloaded")

        # Fast, minimal wait: only wait for the price node.
        try:
            await page.wait_for_selector("div.YMlKec.fxKbKc", timeout=8000)
        except PlaywrightTimeoutError:
            return {
                "ticker": ticker.upper(),
                "exchange": exchange.upper(),
                "url": url,
                "error": "price selector timeout (possible consent/interstitial/blocked)",
            }

        # Read price
        price_text = await page.locator("div.YMlKec.fxKbKc").first.inner_text()
        price = StockScrapper._clean_number(price_text)

        return {
            "ticker": ticker.upper(),
            "exchange": exchange.upper(),
            "url": url,
            "price_text": price_text,
            "price": price,
        }

    @staticmethod
    async def scrape_quotes(
        symbols: List[Tuple[str, str]],
        concurrency: int = 6,
        headless: bool = True,
    ) -> List[Dict[str, object]]:
        """
        Scrape many tickers concurrently while reusing one browser/context.
        symbols: list of (ticker, exchange) like [("AAPL","NASDAQ"), ("SPY","NYSEARCA")]
        """
        sem = asyncio.Semaphore(concurrency)
        results: List[Dict[str, object]] = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                ],
            )

            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1200, "height": 800},
                locale="en-US",
            )

            # Block heavy resources globally for this context
            await context.route("**/*", StockScrapper._route_blocker)

            async def worker(ticker: str, exchange: str):
                async with sem:
                    page = await context.new_page()
                    try:
                        data = await StockScrapper.fetch_quote(page, ticker, exchange)
                        results.append(data)
                    finally:
                        await page.close()

            await asyncio.gather(*(worker(t, ex) for t, ex in symbols))

            await context.close()
            await browser.close()

        return results

    @staticmethod
    def chunk_list(items, size):
        for i in range(0, len(items), size):
            yield items[i:i + size]

    @staticmethod
    async def scrape_in_batches(df=df, batch_size=5, concurrency=6, headless=True):
        symbols = list(zip(df["ticker"], df["exchange"]))
        all_rows = []

        for i in range(0, len(symbols), batch_size):
            batch = symbols[i: i + batch_size]
            print(f"Processing batch {i // batch_size + 1} out of {len(symbols) // batch_size + 1} with {len(batch)} symbols...")

            data = await StockScrapper.scrape_quotes(
                batch, concurrency=concurrency, headless=headless
            )

            # don't block the event loop
            await asyncio.sleep(5)

            now_iso = datetime.now(timezone.utc).isoformat()

            for row in data:
                if "error" in row:
                    print(row.get("ticker"), "ERROR:", row["error"])
                    continue

                ticker = row.get("ticker")
                exchange = row.get("exchange")
                price = row.get("price")

                if ticker and exchange and price is not None:
                    all_rows.append({
                        "ticker": ticker,
                        "exchange": exchange,
                        "price": price,
                        "last_updated": now_iso
                    })
                    print(ticker, exchange, row.get("price_text"))
            

        if not all_rows:
            print("No rows to update.")
            return

        # Upsert in chunks (prevents huge HTTP payloads)
        CHUNK_SIZE = 500

        total = 0
        for chunk in StockScrapper.chunk_list(all_rows, CHUNK_SIZE):
            resp = supabase.table("stocks").upsert(
                chunk,
                on_conflict="ticker,exchange"
            ).execute()

            if getattr(resp, "error", None):
                raise RuntimeError(f"Supabase upsert error: {resp.error}")

            total += len(chunk)

        print(f"Upserted/updated {total} rows.")


