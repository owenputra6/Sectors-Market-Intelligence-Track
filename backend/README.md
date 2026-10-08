# Watcher Backend

FastAPI service that refreshes Sectors data weekly, publishes versioned CSV
snapshots, and serves browse, detail, sector benchmark, and 15-feature duel
responses without live provider calls from HTTP request handlers.

## Routes

| Route | Purpose | Provider credits |
|---|---|---:|
| `GET /health` | Service and snapshot state | 0 |
| `GET /api/v1/data-status` | Current CSV version and next refresh | 0 |
| `GET /api/v1/stocks` | Ranked fingerprint list | 0 |
| `GET /api/v1/stocks/{ticker}` | Five segments, 15 features, P/E evidence | 0 |
| `GET /api/v1/sectors` | Exact subsector median P/E directory | 0 |
| `POST /api/v1/duels` | Direct two-stock report from published CSV | 0 |

Run `python -m app.refresh --check` for local status or `python -m app.refresh`
to refresh only when due. Startup scheduling is controlled by
`WEEKLY_REFRESH_ENABLED`.

For a no-credit local run, set `WEEKLY_REFRESH_ENABLED=false` (this automatically
enables cache-only behavior; `CACHE_ONLY_MODE=true` can also force it). The
scheduler and refresh CLI then make no provider requests. If a complete weekly
snapshot is not present, the API builds an explicitly marked `partial=true`
read-only view from request-cache CSVs already under `backend/data/cache/`;
missing reports are not fabricated. The UI labels this state
`CACHE-ONLY / PARTIAL` and shows available cohort coverage.
From PowerShell, the convenience launcher is `..\start_backend_cache_only.ps1`.

The API key belongs only in `.env`. The Flutter application never receives it.
All terminal logging omits request headers, credentials, and provider bodies.

If Cloudflare returns Error 1010 `browser_signature_banned`, the provider edge
blocked the HTTP transport before authentication. It is not proof that the API
key is invalid; update the client transport first, then contact Sectors support
if the edge continues to block the request.

The weekly worker spaces provider calls by `SECTORS_REQUEST_MIN_INTERVAL_SECONDS`
(2.1 seconds by default). This is deliberate: the first refresh touches many
subsector and company-report endpoints, and a burst can trigger HTTP 429 even
when the credit budget has not been exhausted.

P/E audit fields include the stock sector, exact subsector, official filtered
median, company count, fetch timestamp, and endpoint path. Sectors does not
expose the post-filter sample count in this response, so `valid_pe_count` stays
null rather than being guessed.
