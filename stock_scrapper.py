### OLD FILES ###

import asyncio
import re
from typing import Dict, Optional, List, Tuple
import time

# Pip installed package
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

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


def _clean_number(text: str) -> Optional[float]:
    if not text:
        return None
    s = re.sub(r"[^0-9,.\-]", "", text).replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


async def _route_blocker(route):
    req = route.request
    url = req.url
    if req.resource_type in BLOCK_RESOURCE_TYPES:
        await route.abort()
        return
    if any(x in url for x in BLOCK_URL_SUBSTRINGS):
        await route.abort()
        return
    await route.continue_()


async def fetch_quote(page, ticker: str, exchange: str = "NASDAQ") -> Dict[str, object]:
    """
    Fetch a single quote quickly using an existing Page.
    """
    url = GOOGLE_FINANCE_QUOTE_URL.format(ticker=ticker.upper(), exchange=exchange.upper())

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
    price = _clean_number(price_text)

    return {
        "ticker": ticker.upper(),
        "exchange": exchange.upper(),
        "url": url,
        "price_text": price_text,
        "price": price,
    }


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
                # Small speed help sometimes:
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
        await context.route("**/*", _route_blocker)

        async def worker(ticker: str, exchange: str):
            async with sem:
                page = await context.new_page()
                try:
                    data = await fetch_quote(page, ticker, exchange)
                    results.append(data)
                finally:
                    await page.close()

        await asyncio.gather(*(worker(t, ex) for t, ex in symbols))

        await context.close()
        await browser.close()

    return results


async def main():
    start = time.time()
    symbols = [
        ("AAPL", "NASDAQ"),
        ("MSFT", "NASDAQ"),
        ("TSLA", "NASDAQ"),
        ("SPY", "NYSEARCA"),
        ("NVDA", "NASDAQ"),
    ]

    data = await scrape_quotes(symbols, concurrency=6, headless=True)
    for row in data:
        if "error" in row:
            print(row["ticker"], "ERROR:", row["error"])
        else:
            print(row["ticker"], row["price_text"], row["price"])
    end = time.time()
    print(f"\nTotal time: {end-start} seconds")


if __name__ == "__main__":
    asyncio.run(main())
