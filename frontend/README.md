# Watcher Flutter UI

Responsive light editorial interface for Web, Android, and iOS. It includes:

- a header-free Home page with an inline recommendation list and the boxed
  Compare launcher aligned to its right on wide screens;
- searchable fingerprint ranking with ticker, company-name, or numeric-rank lookup;
- stock detail pages with a prefilled Compare action;
- a local two-stock duel page with deterministic market-intelligence reasoning;
- a working stock swap action with empty Compare defaults;
- score, ranked dominant segment, coverage, and a five-segment paragraph interpretation;
- five animated segment bars;
- auditable P/E versus exact subsector evidence;
- expanded-by-default 15-feature evidence with both values and winner highlights;
- a complete clickable economic-sector directory;
- a dedicated ranking page for every sector, showing every cached company and
  switchable Overall, Valuation, Growth, Financial, Performance, and Dividend ranks;
- expandable missing-feature details; missing pairs remain visible but are
  excluded from every comparison percentage;
- loading, empty, stale, and error states.

The app talks only to the included FastAPI service and contains no Sectors key.

The official winner still comes from the five-segment majority. The backend's
continuous feature-point share adds a capped margin tilt to one point per win
and half a point per valid draw; missing pairs are excluded. The original five
segment cards consume those backend percentages. Profile bars remain segment
wins divided by scheduled opponents.

Generate platform wrappers once:

```powershell
python tool\bootstrap_platforms.py
flutter analyze
flutter test
```

Web:

```powershell
flutter run -d chrome --web-port 5173 `
  --dart-define=API_BASE_URL=http://127.0.0.1:8000
```

Android emulator:

```powershell
flutter run -d emulator-5554 `
  --dart-define=API_BASE_URL=http://10.0.2.2:8000
```

iOS simulator (macOS/Xcode):

```bash
flutter run -d ios --dart-define=API_BASE_URL=http://127.0.0.1:8000
```
