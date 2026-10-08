# Verification record

Run date: 2026-10-01

## Passed in the delivery environment

- Five focused feature-engine unit tests, including continuous margin scoring.
- Direct profile-contract validation for overall/segment rank, neighboring-rank
  evidence, loss-count `Top N`, drawdown, and the original win-count profile
  calculation.
- Python bytecode compilation for backend, tests, and Flutter bootstrap tool.
- Sectors contract fixtures for structured KOMPAS100, sector/subsector filtering,
  and pagination.
- Official exact-subsector `filtered_median_pe` is applied to cross-subsector P/E.
- Same-subsector P/E remains raw; zero and negative P/E cannot win as “cheap”.
- Refresh logs contain sector, subsector, stock P/E, median P/E, relative P/E,
  company count, source time, and CSV publication status.
- Weekly due state survives restarts; a failed refresh retains the prior snapshot.
- Request cache, report payloads, profiles, manifests, and credit ledger are CSV.
- Browse, detail, sector directory, and duel endpoints do not contact Sectors.
- API contract remains five segments and 15 feature evidence rows.
- Older profile CSV payloads are migrated locally without Sectors requests.
- Home and Compare use keyboard-aware autocomplete dropdowns.
- A numeric query such as `5` or `#5` resolves snapshot rank 5.
- Compare begins empty, swap is wired, and the original compact five-card
  segment layout is retained. Missing-data warnings are reconciled from both
  each segment summary and its feature rows before opening a small dropdown.
- “What this means” remains one paragraph, covers all five segment win counts,
  and the 30-day shift section is absent.
- AI navigation and external AI dependencies are absent.
- CORS preflight succeeds for arbitrary localhost Flutter Web ports.
- Dart delimiter balance, local imports, and backend endpoint names were
  cross-checked. Flutter SDK was not available in the delivery environment,
  so the commands below remain the authoritative platform validation.
- No `.env`, API key, live response, or generated data cache is included.

## Run on the development computer

A platform build requires the locally installed Flutter SDK. After generating
official wrappers, run:

```powershell
cd frontend
python tool\bootstrap_platforms.py
flutter analyze
flutter test
flutter build web
```

Android builds run on Windows. iOS compilation and simulator tests require
macOS and Xcode.

Live provider validation requires the user's Sectors API key. The first run
will print all retrieved subsector benchmark values in the backend terminal.
