import os
import requests
import pandas as pd
from datetime import datetime, timezone
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Ticker / company name resolution
# ---------------------------------------------------------------------------

_nasdaq = pd.read_json("JSON/nasdaq.json")
_nyse = pd.read_json("JSON/nyse.json")
_stocks_df = pd.concat([_nasdaq, _nyse], axis=0, ignore_index=True)


def resolve_inputs(
    ticker: Optional[str],
    company_name: Optional[str],
) -> tuple[str, str]:
    """Return (ticker, company_name), filling in whichever is missing via the local JSON lookup."""
    if not ticker and not company_name:
        raise ValueError("At least one of ticker or company_name must be provided.")

    if ticker and not company_name:
        row = _stocks_df[_stocks_df["ticker"].str.upper() == ticker.upper()]
        company_name = row.iloc[0]["name"] if not row.empty else ticker

    if company_name and not ticker:
        row = _stocks_df[_stocks_df["name"].str.lower() == company_name.lower()]
        ticker = row.iloc[0]["ticker"].upper() if not row.empty else company_name.upper()

    return ticker.upper(), company_name


# ---------------------------------------------------------------------------
# Provider base / exception
# ---------------------------------------------------------------------------

class ProviderError(Exception):
    pass


class NewsProvider:
    name: str = "base"

    def fetch(self, ticker: str, company_name: str, max_articles: int) -> list[dict]:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# newsdata.io provider
# ---------------------------------------------------------------------------

class NewsdataProvider(NewsProvider):
    name = "newsdata"
    BASE_URL = "https://newsdata.io/api/1/latest"

    def fetch(self, ticker: str, company_name: str, max_articles: int) -> list[dict]:
        api_key = os.getenv("NEWSDATA_API_KEY")
        if not api_key:
            raise ProviderError("NEWSDATA_API_KEY not set")

        params = {
            "apikey": api_key,
            "q": company_name,
            "language": "en",
            "size": min(max_articles, 10),  # free tier max is 10
        }

        resp = requests.get(self.BASE_URL, params=params, timeout=10)

        if resp.status_code == 429:
            raise ProviderError("newsdata.io rate limit exceeded")
        if resp.status_code == 401:
            raise ProviderError("newsdata.io invalid API key")
        if not resp.ok:
            raise ProviderError(f"newsdata.io error {resp.status_code}: {resp.text[:200]}")

        data = resp.json()
        articles = data.get("results", [])

        results = []
        for a in articles:
            results.append({
                "headline": a.get("title") or "",
                "url": a.get("link") or "",
                "summary": a.get("description") or "",
                "published_at": a.get("pubDate") or "",
                "source": a.get("source_name") or "",
            })
        return results


# ---------------------------------------------------------------------------
# newsapi.org provider
# ---------------------------------------------------------------------------

class NewsApiProvider(NewsProvider):
    name = "newsapi"
    BASE_URL = "https://newsapi.org/v2/everything"

    def fetch(self, ticker: str, company_name: str, max_articles: int) -> list[dict]:
        api_key = os.getenv("NEWSAPI_KEY")
        if not api_key:
            raise ProviderError("NEWSAPI_KEY not set")

        params = {
            "apiKey": api_key,
            "q": company_name,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": min(max_articles, 100),
        }

        resp = requests.get(self.BASE_URL, params=params, timeout=10)

        if resp.status_code == 429:
            raise ProviderError("newsapi.org rate limit exceeded")
        if resp.status_code == 401:
            raise ProviderError("newsapi.org invalid API key")
        if not resp.ok:
            raise ProviderError(f"newsapi.org error {resp.status_code}: {resp.text[:200]}")

        data = resp.json()
        if data.get("status") != "ok":
            raise ProviderError(f"newsapi.org returned status={data.get('status')}: {data.get('message')}")

        articles = data.get("articles", [])

        results = []
        for a in articles:
            results.append({
                "headline": a.get("title") or "",
                "url": a.get("url") or "",
                "summary": a.get("description") or "",
                "published_at": a.get("publishedAt") or "",
                "source": (a.get("source") or {}).get("name") or "",
            })
        return results


# ---------------------------------------------------------------------------
# Provider registry
# ---------------------------------------------------------------------------

_PROVIDERS: dict[str, NewsProvider] = {
    "newsdata": NewsdataProvider(),
    "newsapi": NewsApiProvider(),
}


# ---------------------------------------------------------------------------
# Main tool: get_stock_news
# ---------------------------------------------------------------------------

def get_stock_news(
    ticker: Optional[str] = None,
    company_name: Optional[str] = None,
    max_articles: int = 10,
    providers: list[str] = ["newsdata", "newsapi"],
) -> list[dict]:
    """
    Fetch recent news articles for a company or stock.

    Returns a list of dicts with keys:
        headline, url, summary, published_at, source
    """
    ticker, company_name = resolve_inputs(ticker, company_name)

    last_error = None
    for provider_name in providers:
        provider = _PROVIDERS.get(provider_name)
        if provider is None:
            continue
        try:
            articles = provider.fetch(ticker, company_name, max_articles)
            if articles:
                return articles
        except ProviderError as e:
            print(f"[news_tool] {provider_name} failed: {e}")
            last_error = e

    raise RuntimeError(
        f"All news providers failed for {company_name} ({ticker}). Last error: {last_error}"
    )


GET_STOCK_NEWS_SCHEMA = {
    "name": "get_stock_news",
    "description": (
        "Fetch the most recent news articles about a company or stock. "
        "Provide at least one of ticker or company_name."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "ticker": {
                "type": "string",
                "description": "Stock ticker symbol, e.g. AAPL",
            },
            "company_name": {
                "type": "string",
                "description": "Company name, e.g. Apple Inc",
            },
            "max_articles": {
                "type": "integer",
                "description": "Maximum number of articles to return (default 10)",
                "default": 10,
            },
        },
        "required": [],
    },
}


# ---------------------------------------------------------------------------
# NotebookLM integration
# ---------------------------------------------------------------------------

FISCALIQ_NOTEBOOK_NAME = "FiscalIQ"


async def add_news_to_notebooklm(
    articles: list[dict],
    ticker: str,
    company_name: str,
    mcp_client,
) -> str:
    """
    Add news article URLs to the FiscalIQ NotebookLM notebook, then query for a summary.

    Creates the FiscalIQ notebook if it does not already exist.
    Returns a human-readable summary report string.

    mcp_client must expose an async call_tool(tool_name, arguments) method.
    """
    # 1. Find or create the FiscalIQ notebook
    list_result = await mcp_client.call_tool("notebook_list", {})
    notebooks = list_result if isinstance(list_result, list) else (list_result.get("notebooks") or [])

    notebook_id = None
    for nb in notebooks:
        if nb.get("title") == FISCALIQ_NOTEBOOK_NAME or nb.get("name") == FISCALIQ_NOTEBOOK_NAME:
            notebook_id = nb.get("id") or nb.get("notebook_id")
            break

    if notebook_id is None:
        create_result = await mcp_client.call_tool("notebook_create", {"title": FISCALIQ_NOTEBOOK_NAME})
        notebook_id = (
            create_result.get("id")
            or create_result.get("notebook_id")
            or create_result.get("notebookId")
        )

    # 2. Add each article URL as a source
    added = []
    for article in articles:
        url = article.get("url")
        if not url:
            continue
        try:
            await mcp_client.call_tool("source_add", {"notebook_id": notebook_id, "url": url})
            added.append(article)
        except Exception as e:
            print(f"[news_tool] Failed to add source {url}: {e}")

    # 3. Query for a summary
    query_prompt = (
        f"Summarize all the recent news about {company_name} ({ticker}). "
        "What are the key themes, risks, and developments?"
    )
    query_result = await mcp_client.call_tool(
        "notebook_query",
        {"notebook_id": notebook_id, "query": query_prompt},
    )
    summary_text = (
        query_result
        if isinstance(query_result, str)
        else (query_result.get("answer") or query_result.get("response") or str(query_result))
    )

    # 4. Format as human-readable report
    lines = [
        f"=== FiscalIQ News Summary: {company_name} ({ticker}) ===",
        "",
        summary_text,
        "",
        f"Sources ({len(added)} articles added):",
    ]
    for i, a in enumerate(added, 1):
        pub = a.get("published_at", "")
        source = a.get("source", "")
        lines.append(f"{i}. {a.get('headline', '')} — {source} ({pub})")
        lines.append(f"   {a.get('url', '')}")

    return "\n".join(lines)


ADD_NEWS_TO_NOTEBOOKLM_SCHEMA = {
    "name": "add_news_to_notebooklm",
    "description": (
        "Add fetched news articles to the FiscalIQ NotebookLM notebook and return a "
        "human-readable AI-generated summary of the news. Creates the notebook if it doesn't exist."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "articles": {
                "type": "array",
                "description": "List of article dicts from get_stock_news",
                "items": {"type": "object"},
            },
            "ticker": {"type": "string", "description": "Stock ticker, e.g. AAPL"},
            "company_name": {"type": "string", "description": "Company name, e.g. Apple Inc"},
        },
        "required": ["articles", "ticker", "company_name"],
    },
}


async def delete_fiscaliq_notebook(mcp_client) -> bool:
    """
    Delete the FiscalIQ NotebookLM notebook.
    Returns True if deleted, False if not found.

    mcp_client must expose an async call_tool(tool_name, arguments) method.
    """
    list_result = await mcp_client.call_tool("notebook_list", {})
    notebooks = list_result if isinstance(list_result, list) else (list_result.get("notebooks") or [])

    for nb in notebooks:
        if nb.get("title") == FISCALIQ_NOTEBOOK_NAME or nb.get("name") == FISCALIQ_NOTEBOOK_NAME:
            notebook_id = nb.get("id") or nb.get("notebook_id")
            await mcp_client.call_tool("notebook_delete", {"notebook_id": notebook_id, "confirm": True})
            return True

    return False


DELETE_FISCALIQ_NOTEBOOK_SCHEMA = {
    "name": "delete_fiscaliq_notebook",
    "description": "Delete the FiscalIQ NotebookLM notebook and all its sources.",
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

