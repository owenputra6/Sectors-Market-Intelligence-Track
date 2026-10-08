# Watcher — Indonesian Stock Intelligence

> **Watcher stands watch over Indonesia's market, following every signal and
> carrying the clearest stock intelligence back to you.**

Watcher is a Flutter Web, Android, and iOS application backed by FastAPI. It
compares Indonesian stocks using a local, versioned CSV snapshot. The interface
shows when that snapshot was retrieved and never presents cached coverage as
live market data.

The empty/demo state uses the requested `September 2027` label. As soon as a
published snapshot is available, Watcher replaces it with the snapshot's real
`fetched_at` month and year.

Watcher is a relative screening tool, not investment advice or a price target.

## What Watcher provides

- Search by ticker, company name, `5`, or `#5`, with visible recommendations
  and keyboard Up, Down, and Enter navigation.
- A compact two-stock launcher and a complete comparison page.
- Fifteen auditable features across Valuation, Growth, Financial, Performance,
  and Dividend.
- Exact-subsector normalization for cross-sector comparisons.
- Continuous feature-point percentages and the original five-segment verdict.
- Missing or invalid pairs that remain visible but never enter the denominator.
- A clickable sector directory with company rankings switchable by Overall,
  Valuation, Growth, Financial, Performance, and Dividend.
- Deterministic market-intelligence explanations without an OpenAI API.
- Cache-only browsing and comparisons that consume zero Sectors credits.

## Valid and missing features

A feature is valid only when both stocks have usable comparable values. Missing
values, non-positive valuation inputs, and incomplete pairs remain visible in
the evidence dropdown, but produce no point and add nothing to the denominator.

Example: a three-feature segment containing two valid wins for stock A and one
missing pair displays `2 valid`, `1 missing`, and `100% / 0%`. It must never
display `3 valid` and `1 missing`.

## The 15 features

| Segment | Features |
|---|---|
| Valuation | P/E relative to subsector, P/B relative to subsector, price relative to Sectors intrinsic value |
| Growth | Annual revenue growth, annual earnings growth, latest-quarter earnings YoY |
| Financial | ROE versus peers, ROA versus peers, net margin versus peers |
| Performance | 12-month total-return proxy, return versus peers, position within the 52-week range |
| Dividend | TTM yield, five-year average yield, payout ratio |

For different subsectors, P/E and P/B are divided by their exact subsector
medians. ROE, ROA, margin, and relative return use the difference from their
exact subsector peer medians. Companies in the same subsector use raw comparable
values.

## Project structure

```text
backend/                       FastAPI, feature engine, CSV cache, tests
frontend/                      Flutter Web, Android, and iOS application
refresh_selected_sectors.py    Interactive current-data retrieval
start_backend_cache_only.ps1   Safe local backend without provider requests
start_backend.ps1              Backend with the optional weekly scheduler
start_web.ps1                  Flutter Web launcher
```

## Deploy on Vercel (no separate API host)

Watcher can be deployed as two Vercel projects under one account: the FastAPI
backend and the compiled Flutter Web client. The FastAPI entry point is already
`backend/app/main.py`; `backend/vercel.json` explicitly includes the cached CSV
files in the Python function bundle.

Before deploying, ensure the cache-only dataset is intentionally tracked. The
provider request cache contains no API key, but it is required when there is no
published weekly snapshot:

```powershell
git add -f backend/data/cache
git commit -m "data: add cache-only deployment dataset"
git push
```

Deploy the backend first. From `backend/`, run:

```powershell
npx vercel@latest --prod
```

Use a separate Vercel project name such as `watcher-api`. In the backend
project's Vercel environment variables, set `CACHE_ONLY_MODE=true` and
`WEEKLY_REFRESH_ENABLED=false`. Do not set `SECTORS_API_KEY`.

After Vercel returns the backend URL, build and deploy the frontend:

```powershell
cd frontend
flutter build web --release --dart-define=API_BASE_URL=https://watcher-api.vercel.app
cd build\\web
npx vercel@latest --prod
```

Copy the frontend URL into the backend project's Vercel variable
`CORS_ORIGINS`, then redeploy the backend with `npx vercel@latest --prod` from
`backend/`. The two projects may remain private in GitHub; Vercel CLI deploys
the files directly from the local project folder.

## First setup on Windows

```powershell
cd watcher_fullstack_v1\backend
conda activate torch
python -m pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```

`SECTORS_API_KEY` may remain empty while using existing data. Never commit
`backend/.env`.

Prepare Flutter once:

```powershell
cd ..\frontend
python tool\bootstrap_platforms.py
flutter analyze
flutter test
```

## Run from the included CSV data

Terminal 1:

```powershell
cd watcher_fullstack_v1
.\start_backend_cache_only.ps1
```

Terminal 2:

```powershell
cd watcher_fullstack_v1
.\start_web.ps1
```

- Backend: http://127.0.0.1:8000
- API docs: http://127.0.0.1:8000/docs
- Flutter Web: http://127.0.0.1:5173

Browsing, profiles, sector rankings, and duels now read CSV only and make no
Sectors request.

## Retrieve the newest selected sectors

Run the single interactive script from the project root:

```powershell
python refresh_selected_sectors.py
```

The script:

1. Reads `backend/.env`.
2. Securely asks for `SECTORS_API_KEY` only when it is missing.
3. Reads the official Sectors taxonomy.
4. Asks how many sectors to retrieve and which sectors they are.
5. Resolves every company in those sectors, not merely a hard-coded top list.
6. Shows a conservative credit estimate and the current weekly ledger.
7. Requires an explicit maximum-credit authorization and the word `RUN`.
8. Reuses all fresh request-cache CSV files.
9. Publishes the completed combined snapshot atomically.

If a rate limit, network failure, or credit cap interrupts the run, completed
requests remain cached and the previous published snapshot remains active. Run
the same command later to continue without repeating fresh requests.

One Company Report requests five sections:

```text
overview, valuation, financials, dividend, peers
```

Retrieving every company across several sectors can therefore require many
credits. Watcher's script never silently lifts the budget.

## Optional scheduled refresh

Configure `backend/.env`:

```dotenv
SECTORS_API_KEY=your_raw_key
WEEKLY_REFRESH_ENABLED=true
CACHE_ONLY_MODE=false
WEEKLY_CREDIT_BUDGET=550
SECTORS_REQUEST_MIN_INTERVAL_SECONDS=2.1
```

Then run:

```powershell
.\start_backend.ps1
```

The scheduler checks once per minute but refreshes only when the persisted
snapshot is due. A file lock prevents multiple workers from refreshing at once.

## CSV data and cache

```text
backend/data/cache/              Raw successful request cache
backend/data/weekly/current.csv  Active snapshot pointer
backend/data/weekly/credits.csv  Durable weekly credit ledger
backend/data/weekly/snapshots/   Versioned published snapshots
```

Do not delete `credits.csv` to bypass the budget. A failed provider request can
already have consumed a credit, so Watcher records the charge before sending.

## Android and iOS

Android emulator:

```powershell
cd frontend
flutter run -d emulator-5554 `
  --dart-define=API_BASE_URL=http://10.0.2.2:8000
```

iOS requires macOS and Xcode:

```bash
cd frontend
flutter run -d ios --dart-define=API_BASE_URL=http://127.0.0.1:8000
```

For a physical device, replace `127.0.0.1` with the computer's LAN address and
allow port 8000 through the firewall.

## API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Backend and snapshot status |
| GET | `/api/v1/data-status` | Retrieval and cache status |
| GET | `/api/v1/stocks` | Browse cached stocks |
| GET | `/api/v1/stocks/{ticker}` | Stock fingerprint |
| GET | `/api/v1/sectors` | Subsector benchmarks |
| POST | `/api/v1/duels/estimate` | Zero-credit availability check |
| POST | `/api/v1/duels` | Run a local duel |

Interactive API endpoints never trigger a provider refresh.

## Validation

Backend tests use local fixtures and never call Sectors:

```powershell
cd backend
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

Flutter:

```powershell
cd frontend
flutter analyze
flutter test
```

## Limitations

- Snapshot coverage and retrieval time are disclosed in the UI; they are not
  guarantees of current market conditions.
- Performance uses market-cap change plus dividend yield as a total-return
  proxy rather than verified adjusted-price history.
- `intrinsic_value` is supplied by Sectors, not an independently reconstructed
  DCF.
- A higher payout ratio wins under the current rule but is not automatically
  financially healthier.
- Rankings from partial cache coverage must not be interpreted as full-market
  rankings.
