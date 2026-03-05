# Fiscal-IQ Architecture Decisions

## 1. Database & Auth — Supabase (`db_functions.py`)

**Decision:** Use Supabase as the backend for user accounts, portfolios, and stock holdings.

**Why:**
- Provides Postgres + a built-in auth system (sign-up, sign-in, JWT sessions) without standing up a separate auth server.
- Row-Level Security (RLS) policies enforce that users can only read/write their own data, so the app code never has to manually filter by `user_id` — the database rejects unauthorized access at the query level.
- The Python client (`supabase-py`) mirrors the PostgREST query API, keeping data access calls concise.
- A separate `SUPABASE_SERVICE_KEY` is used only for admin operations (e.g. deleting auth users), keeping the publishable key scoped to user-facing operations.

---

## 2. Stock Price Scraping — Playwright (`db_functions.py → StockScrapper`)

**Decision:** Scrape Google Finance for live stock prices using Playwright (headless Chromium) rather than a paid market data API.

**Why:**
- Avoids API costs for price data during early development.
- Playwright can handle JavaScript-rendered pages that a simple `requests` call cannot.
- Resource blocking (images, media, fonts, analytics) is applied globally to the browser context to minimize latency per page load.
- A shared browser context with a semaphore-controlled concurrency pool (`scrape_quotes`) reuses one browser instance across many tickers, avoiding the overhead of launching a new browser per request.
- Batching with a sleep between batches (`scrape_in_batches`) respects rate limits and prevents IP blocks.
- Results are upserted to Supabase in chunks of 500 to avoid large HTTP payloads.

---

## 3. Ticker / Company Name Resolution — Local JSON (`news_tool.py`)

**Decision:** Resolve ticker ↔ company name lookups using the bundled `JSON/nasdaq.json` and `JSON/nyse.json` files rather than an external API.

**Why:**
- Zero latency — no network call required for a lookup that happens on every news request.
- The files already existed in the project (used by `StockScrapper`) so reusing them adds no new dependency.
- Handles the case where a model provides only a ticker (needs a company name for keyword-based news APIs) or only a name (needs a ticker for display).

---

## 4. News Fetching — Multi-Provider with Fallback (`news_tool.py`)

**Decision:** Implement two news providers (newsdata.io, newsapi.org) behind a common interface, tried in priority order with automatic fallback.

**Why:**
- Both services have free-tier rate limits. When one is exhausted the tool continues working instead of failing outright.
- A `ProviderError` exception signals a recoverable failure (rate limit, bad key) vs. a programming error, so the fallback loop only catches provider-level issues.
- Each provider is a class with a single `fetch()` method. Adding a new provider in the future requires only a new class and one line in the registry dict — no changes to the calling code.
- newsdata.io is tried first because its `latest` endpoint returns more timely results; newsapi.org is the fallback.

---

## 5. Model-Agnostic Tool Design — Plain Python + Schema Dict (`news_tool.py`)

**Decision:** Expose tools as plain Python functions alongside a separate `TOOL_SCHEMA` dict rather than hard-coding them into any specific framework (Claude, OpenAI, LangChain).

**Why:**
- The same function can be called directly in a script, wrapped in a Claude `tool_use` block, registered as an OpenAI function, or used in a LangChain tool — without modifying the function itself.
- The schema dict follows the JSON Schema / OpenAI function-calling format, which is the lowest common denominator supported by all major model APIs.
- Keeping logic and schema separate means the schema can be updated (e.g. adding a parameter description) without touching the implementation.

---

## 6. NotebookLM Integration — Injected MCP Client (`news_tool.py`)

**Decision:** The `add_news_to_notebooklm` and `delete_fiscaliq_notebook` functions accept an `mcp_client` argument rather than constructing one internally.

**Why:**
- The calling agent loop (Claude Code, a custom script, etc.) controls the MCP connection lifecycle. Constructing a client inside the function would make it impossible for the caller to share a single authenticated session across multiple tool calls.
- Dependency injection keeps the functions unit-testable — tests can pass a mock client without needing a real NotebookLM connection.
- This is consistent with the model-agnostic philosophy: the tool does not care whether the MCP client comes from Anthropic's SDK, a generic MCP library, or a hand-rolled wrapper.

### notebooklm-mcp-cli reference
- **Package:** `notebooklm-mcp-cli` (installed at `C:\Users\dougl\.notebooklm-mcp-cli`)
- **Install:** `uv tool install notebooklm-mcp-cli`
- **Login:** `nlm login`
- **Auto-configure for Claude Code:** `nlm setup add claude-code`
- **MCP server binary:** `notebooklm-mcp` (launched as subprocess, communicates via stdio)
- **Protocol:** JSON-RPC 2.0 over stdio
- **Initialize handshake:** Send `initialize` request, receive response, then send `notifications/initialized`
- **Tool call format:** `{ "method": "tools/call", "params": { "name": "...", "arguments": {...} } }`
- **Key tools:** `notebook_list`, `notebook_create`, `source_add`, `notebook_query`, `notebook_delete`
- **Response format:** `result.content` is a list of `{ type: "text", text: "..." }` objects
- **Note:** Uses undocumented internal APIs — may break with NotebookLM updates.

**Decision:** Use a single persistent notebook named "FiscalIQ" rather than one notebook per company or per session.

**Why:**
- A single shared notebook accumulates context over time, making NotebookLM's AI-generated summaries progressively richer as more sources are added.
- The user can explicitly delete it (`delete_fiscaliq_notebook`) when they want a clean slate, giving them control without automatic cleanup that could discard valuable sources.
- Creating a new notebook per query would quickly fill the user's NotebookLM workspace with dozens of throwaway notebooks.

---

## 7. Summary Output — Human-Readable Formatted String

**Decision:** `add_news_to_notebooklm` returns a plain-text formatted report (header, summary paragraph, numbered source list) rather than a raw JSON object.

**Why:**
- The output is intended to be read by a person or passed directly to a model's context window as readable text. JSON would require an additional parsing/formatting step before it is useful in either case.
- A consistent format (header → summary → sources) makes the output easy to display in a UI, log to a file, or include in a larger report without further transformation.
