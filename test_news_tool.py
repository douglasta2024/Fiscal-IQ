"""
Tests for news_tool.py

Sections:
  1. resolve_inputs         — pure logic, no network, no API keys needed
  2. NewsdataProvider       — mocked HTTP
  3. NewsApiProvider        — mocked HTTP
  4. get_stock_news         — mocked providers
  5. add_news_to_notebooklm — mocked MCP client
  6. delete_fiscaliq_notebook — mocked MCP client
  7. Schema structure       — sanity checks on the exported schema dicts
  8. Live smoke test        — real network call, skipped if key absent

Run all unit tests (no network required):
    python -m pytest test_news_tool.py -v

Run everything including the live smoke test:
    python -m pytest test_news_tool.py -v -m ""
"""

import asyncio
import os
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from news_tool import (
    resolve_inputs,
    ProviderError,
    NewsdataProvider,
    NewsApiProvider,
    get_stock_news,
    add_news_to_notebooklm,
    delete_fiscaliq_notebook,
    FISCALIQ_NOTEBOOK_NAME,
    GET_STOCK_NEWS_SCHEMA,
    ADD_NEWS_TO_NOTEBOOKLM_SCHEMA,
    DELETE_FISCALIQ_NOTEBOOK_SCHEMA,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_ARTICLES = [
    {
        "headline": "Apple hits all-time high",
        "url": "https://example.com/apple-high",
        "summary": "Shares rose 3% today.",
        "published_at": "2025-01-01T12:00:00Z",
        "source": "Reuters",
    },
    {
        "headline": "Apple new product launch",
        "url": "https://example.com/apple-launch",
        "summary": "New device announced.",
        "published_at": "2025-01-02T09:00:00Z",
        "source": "Bloomberg",
    },
]


def make_mock_response(status_code=200, json_body=None, text=""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.ok = status_code < 400
    resp.json.return_value = json_body or {}
    resp.text = text
    return resp


# ---------------------------------------------------------------------------
# 1. resolve_inputs
# ---------------------------------------------------------------------------

class TestResolveInputs:
    def test_both_provided_returns_as_is(self):
        ticker, name = resolve_inputs("AAPL", "Apple Inc")
        assert ticker == "AAPL"
        assert name == "Apple Inc"

    def test_ticker_only_resolves_name(self):
        ticker, name = resolve_inputs("AAPL", None)
        assert ticker == "AAPL"
        # Should fill in a company name (non-empty)
        assert name and isinstance(name, str)

    def test_company_name_only_resolves_ticker(self):
        # "Apple Inc" is the exact name in the JSON; use a known mapping
        ticker, name = resolve_inputs(None, "Apple Inc.")
        assert ticker == "AAPL"
        assert name == "Apple Inc."

    def test_unknown_ticker_falls_back_to_ticker_as_name(self):
        ticker, name = resolve_inputs("ZZZZ_UNKNOWN", None)
        assert ticker == "ZZZZ_UNKNOWN"
        assert name == "ZZZZ_UNKNOWN"

    def test_unknown_company_falls_back_to_uppercased_name(self):
        ticker, name = resolve_inputs(None, "Nonexistent Corp XYZ")
        assert ticker == "NONEXISTENT CORP XYZ"
        assert name == "Nonexistent Corp XYZ"

    def test_ticker_uppercased(self):
        ticker, _ = resolve_inputs("aapl", "Apple Inc")
        assert ticker == "AAPL"

    def test_neither_raises(self):
        with pytest.raises(ValueError, match="At least one"):
            resolve_inputs(None, None)

    def test_empty_strings_raise(self):
        with pytest.raises(ValueError):
            resolve_inputs("", "")


# ---------------------------------------------------------------------------
# 2. NewsdataProvider
# ---------------------------------------------------------------------------

NEWSDATA_RESPONSE = {
    "status": "success",
    "results": [
        {
            "title": "Apple Q4 results",
            "link": "https://newsdata.io/article/1",
            "description": "Apple beat estimates.",
            "pubDate": "2025-01-01 10:00:00",
            "source_name": "TechCrunch",
        }
    ],
}


class TestNewsdataProvider:
    def setup_method(self):
        self.provider = NewsdataProvider()

    def test_fetch_returns_normalized_fields(self):
        with patch.dict(os.environ, {"NEWSDATA_API_KEY": "test_key"}):
            with patch("news_tool.requests.get") as mock_get:
                mock_get.return_value = make_mock_response(200, NEWSDATA_RESPONSE)
                results = self.provider.fetch("AAPL", "Apple Inc", 5)

        assert len(results) == 1
        a = results[0]
        assert a["headline"] == "Apple Q4 results"
        assert a["url"] == "https://newsdata.io/article/1"
        assert a["summary"] == "Apple beat estimates."
        assert a["published_at"] == "2025-01-01 10:00:00"
        assert a["source"] == "TechCrunch"

    def test_missing_api_key_raises_provider_error(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("NEWSDATA_API_KEY", None)
            with pytest.raises(ProviderError, match="NEWSDATA_API_KEY not set"):
                self.provider.fetch("AAPL", "Apple Inc", 5)

    def test_rate_limit_raises_provider_error(self):
        with patch.dict(os.environ, {"NEWSDATA_API_KEY": "test_key"}):
            with patch("news_tool.requests.get") as mock_get:
                mock_get.return_value = make_mock_response(429)
                with pytest.raises(ProviderError, match="rate limit"):
                    self.provider.fetch("AAPL", "Apple Inc", 5)

    def test_invalid_key_raises_provider_error(self):
        with patch.dict(os.environ, {"NEWSDATA_API_KEY": "bad_key"}):
            with patch("news_tool.requests.get") as mock_get:
                mock_get.return_value = make_mock_response(401)
                with pytest.raises(ProviderError, match="invalid API key"):
                    self.provider.fetch("AAPL", "Apple Inc", 5)

    def test_other_http_error_raises_provider_error(self):
        with patch.dict(os.environ, {"NEWSDATA_API_KEY": "test_key"}):
            with patch("news_tool.requests.get") as mock_get:
                mock_get.return_value = make_mock_response(500, text="Server error")
                with pytest.raises(ProviderError, match="500"):
                    self.provider.fetch("AAPL", "Apple Inc", 5)

    def test_max_articles_capped_at_10(self):
        with patch.dict(os.environ, {"NEWSDATA_API_KEY": "test_key"}):
            with patch("news_tool.requests.get") as mock_get:
                mock_get.return_value = make_mock_response(200, {"results": []})
                self.provider.fetch("AAPL", "Apple Inc", 50)
                call_params = mock_get.call_args[1]["params"]
                assert call_params["size"] == 10

    def test_empty_results_returns_empty_list(self):
        with patch.dict(os.environ, {"NEWSDATA_API_KEY": "test_key"}):
            with patch("news_tool.requests.get") as mock_get:
                mock_get.return_value = make_mock_response(200, {"results": []})
                results = self.provider.fetch("AAPL", "Apple Inc", 5)
                assert results == []


# ---------------------------------------------------------------------------
# 3. NewsApiProvider
# ---------------------------------------------------------------------------

NEWSAPI_RESPONSE = {
    "status": "ok",
    "articles": [
        {
            "title": "Tesla record delivery",
            "url": "https://newsapi.org/article/2",
            "description": "Tesla beat delivery records.",
            "publishedAt": "2025-01-03T08:00:00Z",
            "source": {"name": "CNBC"},
        }
    ],
}


class TestNewsApiProvider:
    def setup_method(self):
        self.provider = NewsApiProvider()

    def test_fetch_returns_normalized_fields(self):
        with patch.dict(os.environ, {"NEWSAPI_KEY": "test_key"}):
            with patch("news_tool.requests.get") as mock_get:
                mock_get.return_value = make_mock_response(200, NEWSAPI_RESPONSE)
                results = self.provider.fetch("TSLA", "Tesla", 5)

        assert len(results) == 1
        a = results[0]
        assert a["headline"] == "Tesla record delivery"
        assert a["url"] == "https://newsapi.org/article/2"
        assert a["summary"] == "Tesla beat delivery records."
        assert a["published_at"] == "2025-01-03T08:00:00Z"
        assert a["source"] == "CNBC"

    def test_missing_api_key_raises_provider_error(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("NEWSAPI_KEY", None)
            with pytest.raises(ProviderError, match="NEWSAPI_KEY not set"):
                self.provider.fetch("TSLA", "Tesla", 5)

    def test_rate_limit_raises_provider_error(self):
        with patch.dict(os.environ, {"NEWSAPI_KEY": "test_key"}):
            with patch("news_tool.requests.get") as mock_get:
                mock_get.return_value = make_mock_response(429)
                with pytest.raises(ProviderError, match="rate limit"):
                    self.provider.fetch("TSLA", "Tesla", 5)

    def test_invalid_key_raises_provider_error(self):
        with patch.dict(os.environ, {"NEWSAPI_KEY": "bad_key"}):
            with patch("news_tool.requests.get") as mock_get:
                mock_get.return_value = make_mock_response(401)
                with pytest.raises(ProviderError, match="invalid API key"):
                    self.provider.fetch("TSLA", "Tesla", 5)

    def test_api_error_status_raises_provider_error(self):
        with patch.dict(os.environ, {"NEWSAPI_KEY": "test_key"}):
            with patch("news_tool.requests.get") as mock_get:
                mock_get.return_value = make_mock_response(
                    200, {"status": "error", "message": "apiKeyInvalid"}
                )
                with pytest.raises(ProviderError, match="apiKeyInvalid"):
                    self.provider.fetch("TSLA", "Tesla", 5)

    def test_empty_articles_returns_empty_list(self):
        with patch.dict(os.environ, {"NEWSAPI_KEY": "test_key"}):
            with patch("news_tool.requests.get") as mock_get:
                mock_get.return_value = make_mock_response(200, {"status": "ok", "articles": []})
                results = self.provider.fetch("TSLA", "Tesla", 5)
                assert results == []


# ---------------------------------------------------------------------------
# 4. get_stock_news
# ---------------------------------------------------------------------------

class TestGetStockNews:
    def _mock_provider(self, name, articles=None, raises=None):
        provider = MagicMock()
        provider.name = name
        if raises:
            provider.fetch.side_effect = raises
        else:
            provider.fetch.return_value = articles or SAMPLE_ARTICLES
        return provider

    def test_returns_articles_from_first_working_provider(self):
        p1 = self._mock_provider("newsdata", SAMPLE_ARTICLES)
        p2 = self._mock_provider("newsapi")

        with patch("news_tool._PROVIDERS", {"newsdata": p1, "newsapi": p2}):
            results = get_stock_news(ticker="AAPL", providers=["newsdata", "newsapi"])

        assert results == SAMPLE_ARTICLES
        p2.fetch.assert_not_called()

    def test_falls_back_to_second_provider_on_error(self):
        p1 = self._mock_provider("newsdata", raises=ProviderError("rate limited"))
        p2 = self._mock_provider("newsapi", SAMPLE_ARTICLES)

        with patch("news_tool._PROVIDERS", {"newsdata": p1, "newsapi": p2}):
            results = get_stock_news(ticker="AAPL", providers=["newsdata", "newsapi"])

        assert results == SAMPLE_ARTICLES

    def test_raises_runtime_error_when_all_fail(self):
        p1 = self._mock_provider("newsdata", raises=ProviderError("p1 fail"))
        p2 = self._mock_provider("newsapi", raises=ProviderError("p2 fail"))

        with patch("news_tool._PROVIDERS", {"newsdata": p1, "newsapi": p2}):
            with pytest.raises(RuntimeError, match="All news providers failed"):
                get_stock_news(ticker="AAPL", providers=["newsdata", "newsapi"])

    def test_skips_unknown_provider_names(self):
        p1 = self._mock_provider("newsdata", SAMPLE_ARTICLES)

        with patch("news_tool._PROVIDERS", {"newsdata": p1}):
            results = get_stock_news(ticker="AAPL", providers=["unknown_provider", "newsdata"])

        assert results == SAMPLE_ARTICLES

    def test_raises_when_neither_ticker_nor_name_given(self):
        with pytest.raises(ValueError):
            get_stock_news()

    def test_accepts_company_name_only(self):
        p1 = self._mock_provider("newsdata", SAMPLE_ARTICLES)
        with patch("news_tool._PROVIDERS", {"newsdata": p1}):
            results = get_stock_news(company_name="Apple Inc", providers=["newsdata"])
        assert results == SAMPLE_ARTICLES

    def test_article_fields_present(self):
        p1 = self._mock_provider("newsdata", SAMPLE_ARTICLES)
        with patch("news_tool._PROVIDERS", {"newsdata": p1}):
            results = get_stock_news(ticker="AAPL", providers=["newsdata"])
        for article in results:
            for field in ("headline", "url", "summary", "published_at", "source"):
                assert field in article, f"Missing field: {field}"


# ---------------------------------------------------------------------------
# 5. add_news_to_notebooklm
# ---------------------------------------------------------------------------

def make_mock_mcp(existing_notebooks=None, notebook_id="nb-123", summary="Great summary."):
    client = MagicMock()

    async def call_tool(tool_name, args):
        if tool_name == "notebook_list":
            return existing_notebooks if existing_notebooks is not None else []
        if tool_name == "notebook_create":
            return {"id": notebook_id}
        if tool_name == "source_add":
            return {"status": "ok"}
        if tool_name == "notebook_query":
            return {"answer": summary}
        if tool_name == "notebook_delete":
            return {"status": "ok"}
        return {}

    client.call_tool = call_tool
    return client


class TestAddNewsToNotebooklm:
    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_creates_notebook_when_not_found(self):
        client = make_mock_mcp(existing_notebooks=[])
        calls = []

        async def tracking_call(tool_name, args):
            calls.append(tool_name)
            return await make_mock_mcp().call_tool(tool_name, args)

        client.call_tool = tracking_call
        self._run(add_news_to_notebooklm(SAMPLE_ARTICLES, "AAPL", "Apple Inc", client))
        assert "notebook_create" in calls

    def test_reuses_existing_fiscaliq_notebook(self):
        existing = [{"title": FISCALIQ_NOTEBOOK_NAME, "id": "existing-id"}]
        client = make_mock_mcp(existing_notebooks=existing)
        calls = []

        async def tracking_call(tool_name, args):
            calls.append((tool_name, dict(args)))
            return await make_mock_mcp(existing_notebooks=existing).call_tool(tool_name, args)

        client.call_tool = tracking_call
        self._run(add_news_to_notebooklm(SAMPLE_ARTICLES, "AAPL", "Apple Inc", client))
        assert "notebook_create" not in [c[0] for c in calls]

    def test_adds_source_for_each_article(self):
        client = make_mock_mcp()
        added_urls = []

        async def tracking_call(tool_name, args):
            if tool_name == "source_add":
                added_urls.append(args.get("url"))
            return await make_mock_mcp().call_tool(tool_name, args)

        client.call_tool = tracking_call
        self._run(add_news_to_notebooklm(SAMPLE_ARTICLES, "AAPL", "Apple Inc", client))
        assert len(added_urls) == len(SAMPLE_ARTICLES)
        for article in SAMPLE_ARTICLES:
            assert article["url"] in added_urls

    def test_skips_articles_with_no_url(self):
        articles_with_empty = [
            {"headline": "No URL article", "url": "", "summary": "", "published_at": "", "source": ""},
            SAMPLE_ARTICLES[0],
        ]
        client = make_mock_mcp()
        added_urls = []

        async def tracking_call(tool_name, args):
            if tool_name == "source_add":
                added_urls.append(args.get("url"))
            return await make_mock_mcp().call_tool(tool_name, args)

        client.call_tool = tracking_call
        self._run(add_news_to_notebooklm(articles_with_empty, "AAPL", "Apple Inc", client))
        assert len(added_urls) == 1

    def test_output_is_human_readable_string(self):
        client = make_mock_mcp(summary="Key themes: earnings, growth.")
        result = self._run(add_news_to_notebooklm(SAMPLE_ARTICLES, "AAPL", "Apple Inc", client))
        assert isinstance(result, str)
        assert "Apple Inc" in result
        assert "AAPL" in result
        assert "Key themes: earnings, growth." in result
        assert "Sources" in result

    def test_output_contains_article_headlines(self):
        client = make_mock_mcp()
        result = self._run(add_news_to_notebooklm(SAMPLE_ARTICLES, "AAPL", "Apple Inc", client))
        for article in SAMPLE_ARTICLES:
            assert article["headline"] in result

    def test_output_contains_article_urls(self):
        client = make_mock_mcp()
        result = self._run(add_news_to_notebooklm(SAMPLE_ARTICLES, "AAPL", "Apple Inc", client))
        for article in SAMPLE_ARTICLES:
            assert article["url"] in result

    def test_handles_source_add_failure_gracefully(self):
        client = make_mock_mcp()

        async def failing_call(tool_name, args):
            if tool_name == "source_add":
                raise Exception("NotebookLM source add failed")
            return await make_mock_mcp().call_tool(tool_name, args)

        client.call_tool = failing_call
        # Should not raise; failed sources are skipped
        result = self._run(add_news_to_notebooklm(SAMPLE_ARTICLES, "AAPL", "Apple Inc", client))
        assert "Sources (0 articles added)" in result

    def test_handles_string_query_result(self):
        client = make_mock_mcp()

        async def call_tool(tool_name, args):
            if tool_name == "notebook_query":
                return "Plain string summary"
            return await make_mock_mcp().call_tool(tool_name, args)

        client.call_tool = call_tool
        result = self._run(add_news_to_notebooklm(SAMPLE_ARTICLES, "AAPL", "Apple Inc", client))
        assert "Plain string summary" in result


# ---------------------------------------------------------------------------
# 6. delete_fiscaliq_notebook
# ---------------------------------------------------------------------------

class TestDeleteFiscaliqNotebook:
    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_returns_true_when_notebook_found_and_deleted(self):
        existing = [{"title": FISCALIQ_NOTEBOOK_NAME, "id": "nb-abc"}]
        client = make_mock_mcp(existing_notebooks=existing)
        result = self._run(delete_fiscaliq_notebook(client))
        assert result is True

    def test_returns_false_when_notebook_not_found(self):
        client = make_mock_mcp(existing_notebooks=[])
        result = self._run(delete_fiscaliq_notebook(client))
        assert result is False

    def test_calls_notebook_delete_with_correct_id(self):
        existing = [{"title": FISCALIQ_NOTEBOOK_NAME, "id": "nb-to-delete"}]
        client = make_mock_mcp(existing_notebooks=existing)
        delete_calls = []

        async def tracking_call(tool_name, args):
            if tool_name == "notebook_delete":
                delete_calls.append(args)
            return await make_mock_mcp(existing_notebooks=existing).call_tool(tool_name, args)

        client.call_tool = tracking_call
        self._run(delete_fiscaliq_notebook(client))
        assert len(delete_calls) == 1
        assert delete_calls[0]["notebook_id"] == "nb-to-delete"

    def test_matches_by_name_field_too(self):
        existing = [{"name": FISCALIQ_NOTEBOOK_NAME, "notebook_id": "nb-xyz"}]
        client = make_mock_mcp(existing_notebooks=existing)
        result = self._run(delete_fiscaliq_notebook(client))
        assert result is True

    def test_ignores_other_notebooks(self):
        existing = [
            {"title": "SomeOtherNotebook", "id": "nb-other"},
            {"title": FISCALIQ_NOTEBOOK_NAME, "id": "nb-fiscal"},
        ]
        client = make_mock_mcp(existing_notebooks=existing)
        delete_calls = []

        async def tracking_call(tool_name, args):
            if tool_name == "notebook_delete":
                delete_calls.append(args)
            return await make_mock_mcp(existing_notebooks=existing).call_tool(tool_name, args)

        client.call_tool = tracking_call
        result = self._run(delete_fiscaliq_notebook(client))
        assert result is True
        assert len(delete_calls) == 1
        assert delete_calls[0]["notebook_id"] == "nb-fiscal"


# ---------------------------------------------------------------------------
# 7. Schema structure
# ---------------------------------------------------------------------------

class TestSchemas:
    def test_get_stock_news_schema_has_required_fields(self):
        s = GET_STOCK_NEWS_SCHEMA
        assert s["name"] == "get_stock_news"
        assert "description" in s
        assert "parameters" in s
        props = s["parameters"]["properties"]
        assert "ticker" in props
        assert "company_name" in props
        assert "max_articles" in props

    def test_add_news_schema_has_required_fields(self):
        s = ADD_NEWS_TO_NOTEBOOKLM_SCHEMA
        assert s["name"] == "add_news_to_notebooklm"
        assert "articles" in s["parameters"]["required"]
        assert "ticker" in s["parameters"]["required"]
        assert "company_name" in s["parameters"]["required"]

    def test_delete_schema_has_no_required_params(self):
        s = DELETE_FISCALIQ_NOTEBOOK_SCHEMA
        assert s["name"] == "delete_fiscaliq_notebook"
        assert s["parameters"]["required"] == []


# ---------------------------------------------------------------------------
# 8. Live smoke test (skipped if NEWSDATA_API_KEY not set)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not os.getenv("NEWSDATA_API_KEY"),
    reason="NEWSDATA_API_KEY not set — skipping live network test",
)
class TestLiveNewsdata:
    def test_get_stock_news_live_returns_articles(self):
        articles = get_stock_news(ticker="AAPL", max_articles=3, providers=["newsdata"])
        assert len(articles) > 0
        for a in articles:
            assert a["headline"]
            assert a["url"]
            print(f"  [{a['source']}] {a['headline']}")
            print(f"    {a['url']}")

    def test_get_stock_news_live_company_name_only(self):
        articles = get_stock_news(company_name="Tesla", max_articles=3, providers=["newsdata"])
        assert len(articles) > 0


if __name__ == "__main__":
    import subprocess, sys
    sys.exit(subprocess.call(["python", "-m", "pytest", __file__, "-v"]))

    # Unit tests only with no newwork or api keys
    # python -m pytest test_news_tool.py -v

    # Include live smoke test
    # python -m pytest test_news_tool.py -v -m ""
