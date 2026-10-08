"""Weekly CSV ingestion. HTTP request handlers only read published snapshots.

Run one scheduler worker; file lock and atomic publication also protect restarts.
No database, no implicit credit consumption from browsing.
"""
from __future__ import annotations

import asyncio
import csv
import json
import logging
import os
import re
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from filelock import FileLock, Timeout
from .feature_engine import snapshot_from_report, finite, run_duel, METRICS, _comparable
from .sectors_client import SectorsClient, normalize_ticker

csv.field_size_limit(16 * 1024 * 1024)
log = logging.getLogger('uvicorn.error')
WEEK = 604800
AXES = ('Valuation', 'Growth', 'Financial', 'Performance', 'Dividend')
AXIS_EXPLANATIONS = {
    'Valuation': 'Relative pricing: P/E, P/B, and price versus Sectors intrinsic value.',
    'Growth': 'Recent revenue and earnings expansion, including the latest quarter YoY.',
    'Financial': 'ROE, ROA, and net margin versus the company\'s operating context.',
    'Performance': '12-month return proxy, return versus peers, and position below the 52-week high.',
    'Dividend': 'Current yield, five-year average yield, and payout ratio under the duel rules.',
}


def utcnow():
    return datetime.now(timezone.utc)


def slug(value):
    return re.sub(r'[^a-z0-9]+', '-', str(value or '').lower()).strip('-')


def read_csv(path):
    if not path.exists():
        return []
    with path.open(encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fields=None):
    rows = list(rows)
    fields = fields or list(dict.fromkeys(k for r in rows for k in r))
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.tmp-', suffix='.csv')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def apply_benchmark(stock, sectors, minimum=5):
    """Never use broad-sector or nearest-peer PE as the sector baseline."""
    row = next((r for r in sectors if slug(r['sub_sector']) == slug(stock.sub_sector)
                and slug(r['sector']) == slug(stock.sector)), None)
    baseline = finite(row.get('filtered_median_pe')) if row else None
    stock.peer_medians['pe_ttm'] = baseline if baseline and baseline > 0 else None
    stock.peer_counts['pe_ttm'] = None  # vendor does not expose filtered sample n
    for key, n in stock.peer_counts.items():
        if key != 'pe_ttm' and (n or 0) < minimum:
            stock.peer_medians[key] = None
    stock.benchmark = {
        'scope': 'sub_sector', 'sector': stock.sector, 'sub_sector': stock.sub_sector,
        'pe_source': ('Sectors ' + row['source'] + ' statistics.filtered_median_pe') if row else None,
        'pe_method': 'vendor_filtered_median', 'pe_median': stock.peer_medians['pe_ttm'],
        'total_companies': int(row['total_companies']) if row and row.get('total_companies') else None,
        'valid_pe_count': None, 'fetched_at': row.get('fetched_at') if row else None,
        'other_metrics_scope': 'exact subsector Company Report peers; target excluded',
        'available': stock.peer_medians['pe_ttm'] is not None,
    }
    return stock


class WeeklyStore:
    def __init__(self, client: SectorsClient):
        self.client = client
        self.root = client.settings.cache_dir.parent / 'weekly'
        self.root.mkdir(parents=True, exist_ok=True)
        self._version = None
        self._profiles = {}
        self._stocks = {}
        self._manifest = {}
        self._sectors = []
        self.last_error = None
        self._next_retry = utcnow()
        self._last_request_monotonic = 0.0
        self._cache_only_attempted = False

    def _respect_provider_rate_limit(self):
        interval = self.client.settings.request_min_interval_seconds
        now = time.monotonic()
        wait = interval - (now - self._last_request_monotonic)
        if wait > 0:
            time.sleep(wait)
        self._last_request_monotonic = time.monotonic()

    def request(self, path, params, cost):
        """Charge a durable conservative ledger BEFORE sending, including failed requests."""
        week = utcnow().strftime('%G-W%V')
        ledger = read_csv(self.root / 'credits.csv')
        spent = sum(int(r['cost']) for r in ledger if r['week'] == week)
        budget = int(os.getenv('WEEKLY_CREDIT_BUDGET', '550'))
        if spent + cost > budget:
            raise RuntimeError(f'Weekly credit budget reached ({spent}+{cost}>{budget}).')
        write_csv(self.root / 'credits.csv', [*ledger, {
            'week': week, 'at': utcnow().isoformat(), 'path': path, 'cost': cost,
        }])
        self._respect_provider_rate_limit()
        req = Request(self.client.settings.base_url + path + '?' + urlencode(params),
                      headers={
                          'Authorization': self.client.settings.api_key,
                          'Accept': 'application/json',
                          'User-Agent': 'sectors-stock-duel-backend/2.0 (+https://docs.sectors.app)',
                      })
        try:
            with urlopen(req, timeout=self.client.settings.request_timeout_seconds,
                         context=self.client.ssl_context) as response:
                payload = json.loads(response.read())
        except HTTPError as exc:
            body = exc.read(2_000).decode('utf-8', errors='replace')
            key = self.client.settings.api_key
            safe_body = body.replace(key, '[REDACTED]') if key else body
            if 'browser_signature_banned' in body or 'Error 1010' in body:
                raise RuntimeError(
                    'Sectors edge blocked the Python transport (Cloudflare 1010 browser signature). '
                    'The API key was not evaluated; use the updated client transport or contact Sectors support.'
                ) from exc
            retry_after = exc.headers.get('Retry-After') if exc.headers else None
            if exc.code == 429:
                suffix = f' Retry-After={retry_after}s.' if retry_after else ''
                raise RuntimeError(
                    f'Sectors rate limit reached for {path}.{suffix} '
                    'The weekly refresh will retain its partial request cache and retry later.'
                ) from exc
            raise RuntimeError(
                f'Sectors request failed: {path} (HTTP {exc.code}): {safe_body[:500]}'
            ) from exc
        except Exception as exc:
            # Never include request headers, key or response body in logs.
            raise RuntimeError(f'Sectors request failed: {path} ({type(exc).__name__})') from exc
        if isinstance(payload, dict) and payload.get('error'):
            raise RuntimeError(f'Sectors rejected {path}')
        return payload

    def cached_request(self, path, params, cost):
        state, cached = self.client._read_cache(path, params)
        # Enforce seven days here even when the legacy client has a different TTL.
        if cached and (utcnow()-datetime.fromisoformat(cached['fetched_at'])).total_seconds() < WEEK:
            return cached['payload'], cached['fetched_at']
        payload = self.request(path, params, cost)
        envelope = self.client._write_cache(path, params, payload)
        return payload, envelope['fetched_at']

    def current(self):
        rows = read_csv(self.root / 'current.csv')
        return rows[0] if rows else {}

    @staticmethod
    def _cache_only_enabled() -> bool:
        cache_flag = os.getenv('CACHE_ONLY_MODE', '').strip().lower()
        refresh_flag = os.getenv('WEEKLY_REFRESH_ENABLED', 'true').strip().lower()
        return cache_flag in {'1', 'true', 'yes', 'on'} or refresh_flag not in {
            '1', 'true', 'yes', 'on'
        }

    def _raw_cache_envelopes(self):
        """Yield valid payloads from the durable request-cache CSVs.

        Cache filenames are content hashes, so this deliberately identifies
        payloads by their documented response shape instead of guessing a URL.
        It is read-only and never calls the provider.
        """
        cache_dir = self.client.settings.cache_dir
        for path in sorted(cache_dir.glob('*.csv')):
            try:
                rows = read_csv(path)
                if not rows:
                    continue
                row = rows[0]
                payload = json.loads(row.get('payload', 'null'))
                fetched = row.get('fetched_at') or utcnow().isoformat()
                datetime.fromisoformat(fetched)
                yield payload, fetched
            except (OSError, csv.Error, ValueError, TypeError, KeyError,
                    json.JSONDecodeError, StopIteration):
                log.warning('Ignoring invalid request-cache CSV %s', path.name)

    def load_partial_cache(self):
        """Build an in-memory, explicitly partial view without network access.

        This is a development/recovery mode for an interrupted weekly run.
        It never writes ``current.csv`` and never treats missing reports as a
        complete cohort; API responses expose ``partial=true`` and coverage.
        """
        self._cache_only_attempted = True
        reports = {}
        sectors = {}
        universe = {}
        universe_may_be_incomplete = False
        for payload, fetched in self._raw_cache_envelopes():
            if isinstance(payload, dict):
                symbol = normalize_ticker(payload.get('symbol', ''))
                if symbol and any(section in payload for section in self.client.settings.report_sections):
                    # Keep the newest response if duplicate cache files exist.
                    previous = reports.get(symbol)
                    if previous is None or fetched > previous[1]:
                        reports[symbol] = (payload, fetched)
                stats = payload.get('statistics')
                sub_sector = payload.get('sub_sector')
                sector = payload.get('sector')
                if isinstance(stats, dict) and sub_sector and sector:
                    key = (slug(sector), slug(sub_sector))
                    previous = sectors.get(key)
                    if previous is None or fetched > previous['fetched_at']:
                        sectors[key] = {
                            'sector': sector, 'sub_sector': sub_sector,
                            'slug': slug(sub_sector),
                            'filtered_median_pe': finite(stats.get('filtered_median_pe')),
                            'filtered_weighted_avg_pe': finite(stats.get('filtered_weighted_avg_pe')),
                            'total_companies': stats.get('total_companies', ''),
                            'valid_pe_count': '', 'fetched_at': fetched,
                            'source': f'/v2/subsector/report/{slug(sub_sector)}/?sections=statistics',
                        }
                results = payload.get('results')
                if isinstance(results, list):
                    pagination = payload.get('pagination') or {}
                    universe_may_be_incomplete = universe_may_be_incomplete or bool(
                        pagination.get('has_next')
                    )
                    for item in results:
                        if isinstance(item, dict) and item.get('symbol'):
                            ticker = normalize_ticker(item['symbol'])
                            universe[ticker] = {
                                'ticker': ticker,
                                'company_name': item.get('company_name'),
                            }

        sectors_rows = list(sectors.values())
        for row in sorted(sectors_rows, key=lambda item: (item['sector'], item['sub_sector'])):
            log.info('CACHED SUBSECTOR %s / %s | median PE=%s | companies=%s | fetched=%s',
                     row['sector'], row['sub_sector'], row['filtered_median_pe'],
                     row['total_companies'], row['fetched_at'])

        cohort_index = os.getenv('COHORT_INDEX', 'KOMPAS100').strip().upper()
        cohort_sector = os.getenv('COHORT_SECTOR', '').strip()
        cohort_subsector = os.getenv('COHORT_SUBSECTOR', '').strip()
        try:
            requested_size = int(os.getenv('COHORT_SIZE', '100'))
        except ValueError:
            requested_size = 100
        top_n = max(2, min(200, requested_size))

        # The screener response is already the result of the configured query;
        # its request identity is intentionally not reconstructed from a hash.
        candidates = list(universe)
        if not candidates:
            candidates = list(reports)
        cohort = candidates[:top_n]
        expected_cohort_size = top_n if universe_may_be_incomplete else len(cohort)
        extras = [normalize_ticker(t) for t in os.getenv('TRACKED_TICKERS', '').split(',') if t.strip()]
        targets = list(dict.fromkeys(cohort + extras))
        if not targets:
            targets = list(reports)

        stocks, report_rows = {}, []
        for ticker in targets:
            cached = reports.get(ticker)
            if not cached:
                continue
            report, fetched = cached
            if not all(section in report for section in self.client.settings.report_sections):
                continue
            stock = apply_benchmark(snapshot_from_report(ticker, report), sectors_rows,
                                    self.client.settings.min_valid_peers)
            # A partial cache must not silently invent a broad-sector PE.
            if not stock.sector or not stock.sub_sector or not stock.benchmark.get('available'):
                continue
            stocks[ticker] = stock
            report_rows.append({'ticker': ticker, 'fetched_at': fetched,
                                'payload': json.dumps(report, allow_nan=False)})
            log.info('CACHE-ONLY STOCK %s | %s / %s | PE=%s / subsector median=%s | relative=%s',
                     ticker, stock.sector, stock.sub_sector, stock.pe_ttm,
                     stock.peer_medians['pe_ttm'],
                     stock.pe_ttm / stock.peer_medians['pe_ttm']
                     if stock.pe_ttm is not None and stock.peer_medians['pe_ttm'] else 'N/A')

        available_cohort = [ticker for ticker in cohort if ticker in stocks]
        # If the screener page was not cached, score the reports we do have;
        # the manifest makes the reduced denominator explicit.
        scoring_cohort = available_cohort if len(available_cohort) >= 2 else list(stocks)
        profiles = self.build_profiles(stocks, scoring_cohort) if stocks else {}
        fetched_values = [row['fetched_at'] for row in sectors_rows] + [row['fetched_at'] for row in report_rows]
        latest = max(fetched_values) if fetched_values else None
        oldest = min(fetched_values) if fetched_values else None
        cohort_name_parts = [part for part in (cohort_index, cohort_sector, cohort_subsector) if part]
        cohort_name = ' · '.join(cohort_name_parts) if cohort_name_parts else f'Top {len(cohort)} cached reports'
        self._stocks, self._profiles, self._sectors = stocks, profiles, sectors_rows
        self._version = f'cache-only-{(latest or utcnow().isoformat()).replace(":", "").replace("+00:00", "Z")}'
        self._manifest = {
            'version': self._version,
            'fetched_at': latest,
            'oldest_source_at': oldest,
            'next_refresh_at': 'disabled',
            'cohort_size': len(scoring_cohort),
            'cohort_size_expected': expected_cohort_size,
            'cohort_size_available': len(available_cohort),
            'cohort_name': cohort_name + ' · cache-only',
            'source': 'Sectors request-cache CSV',
            'partial': True,
            'cache_only': True,
            'missing_reports': max(0, expected_cohort_size - len(available_cohort)),
            'cached_reports': len(stocks),
        }
        if not stocks:
            self.last_error = 'No complete, benchmarked company reports are available in request cache.'
        else:
            self.last_error = None
        log.info('CACHE-ONLY VIEW | reports=%s | cohort=%s/%s | no provider calls',
                 len(stocks), len(available_cohort), len(cohort))

    def due(self):
        current = self.current()
        return not current or utcnow() >= datetime.fromisoformat(current['next_refresh_at'])

    def refresh(self, *, force=False):
        if not self.client.settings.api_key:
            raise RuntimeError('SECTORS_API_KEY is missing. No API calls made.')
        try:
            with FileLock(str(self.root / 'refresh.lock'), timeout=0):
                if not force and not self.due():
                    self.load()
                    return
                self._refresh_locked()
        except Timeout:
            log.info('CSV refresh already running in another worker.')

    def _refresh_locked(self):
        taxonomy, _ = self.cached_request('/subsectors/', {}, 1)
        if not isinstance(taxonomy, list) or not taxonomy:
            raise RuntimeError('Invalid /subsectors/ response; snapshot not published.')
        cohort_sectors = [
            value.strip()
            for value in os.getenv('COHORT_SECTORS', '').split(',')
            if value.strip()
        ]
        selected_sector_slugs = {slug(value) for value in cohort_sectors}
        selected_taxonomy = (
            [entry for entry in taxonomy if entry.get('sector') in selected_sector_slugs]
            if selected_sector_slugs
            else taxonomy
        )
        if selected_sector_slugs and not selected_taxonomy:
            raise RuntimeError('COHORT_SECTORS did not match the Sectors taxonomy.')
        sectors = []
        for entry in selected_taxonomy:
            name = entry.get('subsector')
            if not name or not re.fullmatch(r'[a-z0-9-]+', name):
                raise RuntimeError('Invalid taxonomy slug; no guessed URL will be used.')
            report, fetched = self.cached_request(f'/subsector/report/{name}/', {'sections': 'statistics'}, 1)
            if slug(report.get('sub_sector')) != name or slug(report.get('sector')) != entry['sector']:
                raise RuntimeError(f'Subsector identity mismatch for {name}.')
            stats = report.get('statistics') or {}
            if 'filtered_median_pe' not in stats or 'total_companies' not in stats:
                raise RuntimeError(f'Missing statistics fields for {name}.')
            row = {'sector': report['sector'], 'sub_sector': report['sub_sector'], 'slug': name,
                   'filtered_median_pe': finite(stats['filtered_median_pe']),
                   'filtered_weighted_avg_pe': finite(stats.get('filtered_weighted_avg_pe')),
                   'total_companies': stats['total_companies'], 'valid_pe_count': '',
                   'fetched_at': fetched, 'source': f'/v2/subsector/report/{name}/?sections=statistics'}
            sectors.append(row)
            log.info('SUBSECTOR %s / %s | median PE=%s | companies=%s | filtered n=not supplied | fetched=%s',
                     row['sector'], row['sub_sector'], row['filtered_median_pe'], row['total_companies'], fetched)
        # Resolve the configured cohort dynamically. KOMPAS100 is the default;
        # clearing COHORT_INDEX enables a market-cap or sector/subsector cohort.
        universe, offset = [], 0
        cohort_index = os.getenv('COHORT_INDEX', 'KOMPAS100').strip().upper()
        cohort_sector = os.getenv('COHORT_SECTOR', '').strip()
        cohort_subsector = os.getenv('COHORT_SUBSECTOR', '').strip()
        company_params = {'order_by': '-market_cap', 'limit': '200',
                          'include_query_values': 'true'}
        conditions = []
        if cohort_index:
            conditions.append(f"indices in ['{cohort_index}']")
        if cohort_sectors:
            escaped = [value.replace(chr(39), chr(39) * 2) for value in cohort_sectors]
            conditions.append(
                'sector in [' + ','.join(f"'{value}'" for value in escaped) + ']'
            )
        elif cohort_sector:
            conditions.append(f"sector = '{cohort_sector.replace(chr(39), chr(39) * 2)}'")
        if cohort_subsector:
            conditions.append(f"sub_sector = '{cohort_subsector.replace(chr(39), chr(39) * 2)}'")
        if conditions:
            company_params['where'] = ' and '.join(conditions)
        while True:
            params = {**company_params, 'offset': str(offset)}
            page, _ = self.cached_request('/companies/', params, 1)
            if not isinstance(page, dict) or not isinstance(page.get('results'), list):
                raise RuntimeError('Invalid companies page.')
            universe.extend(page['results'])
            pagination = page.get('pagination', {})
            if not pagination.get('has_next'):
                break
            next_offset = pagination.get('next_offset')
            if not isinstance(next_offset, int) or next_offset <= offset:
                raise RuntimeError('Pagination failed to advance.')
            offset = next_offset
        seen = set()
        universe = [r for r in universe if not (normalize_ticker(r['symbol']) in seen or seen.add(normalize_ticker(r['symbol'])))]
        try:
            requested_size = int(os.getenv('COHORT_SIZE', '100'))
        except ValueError:
            requested_size = 100
        top_n = len(universe) if requested_size <= 0 else max(2, min(200, requested_size))
        cohort = [normalize_ticker(r['symbol']) for r in universe[:top_n]]
        cohort_name_parts = []
        if cohort_index:
            cohort_name_parts.append(cohort_index)
        if cohort_sectors:
            cohort_name_parts.append(' + '.join(cohort_sectors))
        elif cohort_sector:
            cohort_name_parts.append(cohort_sector)
        if cohort_subsector:
            cohort_name_parts.append(cohort_subsector)
        cohort_name = ' · '.join(cohort_name_parts) if cohort_name_parts else f'Top {len(cohort)} market cap'
        cohort_name = f'{cohort_name} · top {len(cohort)}' if (
            len(cohort) != len(universe) or not cohort_index or cohort_sector or cohort_subsector
        ) else cohort_name
        extras = [normalize_ticker(t) for t in os.getenv('TRACKED_TICKERS', '').split(',') if t.strip()]
        targets = list(dict.fromkeys(cohort + extras))
        stocks, report_rows, acquired = {}, [], []
        for ticker in targets:
            if not re.fullmatch('[A-Z0-9]{2,12}', ticker):
                raise RuntimeError('Invalid configured ticker.')
            path, params = self.client._request_identity(ticker)
            report, fetched = self.cached_request(path, params, self.client.section_cost)
            if normalize_ticker(report.get('symbol', '')) != ticker:
                raise RuntimeError(f'Company identity mismatch for {ticker}.')
            if not all(section in report for section in self.client.settings.report_sections):
                raise RuntimeError(f'Incomplete report for {ticker}; previous snapshot retained.')
            stock = apply_benchmark(snapshot_from_report(ticker, report), sectors,
                                    self.client.settings.min_valid_peers)
            if not stock.sub_sector or not stock.benchmark['fetched_at']:
                raise RuntimeError(f'No matching subsector benchmark for {ticker}.')
            stocks[ticker] = stock
            acquired.append(fetched)
            report_rows.append({'ticker': ticker, 'fetched_at': fetched, 'payload': json.dumps(report, allow_nan=False)})
            log.info('STOCK %s | %s / %s | PE=%s / subsector median=%s | relative=%s', ticker,
                     stock.sector, stock.sub_sector, stock.pe_ttm, stock.peer_medians['pe_ttm'],
                     stock.pe_ttm / stock.peer_medians['pe_ttm'] if stock.pe_ttm is not None and stock.peer_medians['pe_ttm'] else 'N/A')
        if len(cohort) < 2:
            raise RuntimeError('Not enough cohort members.')
        profiles = self.build_profiles(stocks, cohort)
        now = utcnow()
        version = now.strftime('%Y%m%dT%H%M%S%fZ')
        folder = self.root / 'snapshots' / version
        write_csv(folder / 'subsectors.csv', sectors)
        write_csv(folder / 'reports.csv', report_rows)
        write_csv(folder / 'universe.csv', [{'ticker': normalize_ticker(r['symbol']), 'company_name': r.get('company_name'),
                                            'cohort': normalize_ticker(r['symbol']) in cohort} for r in universe])
        write_csv(folder / 'stocks.csv', [{k: json.dumps(v) if isinstance(v, (dict, list)) else v
                                         for k, v in stock.public_dict().items()} for stock in stocks.values()])
        write_csv(folder / 'profiles.csv', [{'ticker': t, 'score': p['score'], 'dominant_axis': p['dominant_axis'],
                                           'payload': json.dumps(p, allow_nan=False)} for t, p in profiles.items()])
        earliest = min([datetime.fromisoformat(r['fetched_at']) for r in sectors] + [datetime.fromisoformat(t) for t in acquired])
        write_csv(self.root / 'current.csv', [{'version': version, 'fetched_at': now.isoformat(),
                    'oldest_source_at': earliest.isoformat(), 'next_refresh_at': (earliest+timedelta(days=7)).isoformat(),
                    'cohort_size': len(cohort), 'cohort_name': cohort_name, 'source': 'Sectors API'}])
        self.last_error = None
        self.load()
        log.info('CSV SNAPSHOT PUBLISHED %s | %s profiles | %s subsectors | next=%s', version,
                 len(profiles), len(sectors), self._manifest['next_refresh_at'])

    def build_profiles(self, stocks, cohort):
        profiles = {}
        for ticker, stock in stocks.items():
            wins = losses = draws = unavailable = 0
            axes = {
                axis: {
                    'wins': 0, 'losses': 0, 'draws': 0, 'unavailable': 0,
                    'explanation': AXIS_EXPLANATIONS[axis],
                }
                for axis in AXES
            }
            for opponent in cohort:
                if opponent == ticker:
                    continue
                duel = run_duel(stock, stocks[opponent], max_missing_feature_rate=self.client.settings.max_missing_feature_rate)
                winner = duel['verdict']['winner']
                wins += winner == ticker
                losses += winner == opponent
                draws += winner == 'draw'
                unavailable += winner == 'unavailable'
                for seg in duel['segments']:
                    valid_count = sum(f['reason'] != 'missing_data' for f in duel['features'] if f['segment'] == seg['segment'])
                    result = 'unavailable' if valid_count < 2 else ('wins' if seg['winner'] == ticker else 'draws' if seg['winner'] == 'draw' else 'losses')
                    axis = axes[seg['segment']]
                    axis[result] += 1
            n = len(cohort) - (ticker in cohort)
            coverage = (n - unavailable) / n if n else 0
            available = bool(wins + losses) and coverage >= 1-self.client.settings.max_missing_feature_rate
            for axis in axes.values():
                # Preserve the original profile calculation and bar semantics:
                # segment wins divided by all scheduled opponents. Continuous
                # point share belongs only to a two-stock duel presentation.
                axis['score'] = round(100 * axis['wins'] / n, 2) if n else None
            best = max((row['wins'] for row in axes.values()), default=0)
            dominant = ' / '.join(
                name for name, row in axes.items() if row['wins'] == best
            ) if best else None
            near_high = finite(stock.last_close_price / stock.high_52w) if stock.last_close_price is not None and stock.high_52w else None
            drawdown = max(0.0, 1 - near_high) if near_high is not None else None
            profile = {'ticker': ticker, 'company_name': stock.company_name, 'sector': stock.sector,
                       'sub_sector': stock.sub_sector, 'score': round(100*wins/(wins+losses), 2) if available else None,
                       'wins': wins, 'losses': losses, 'draws': draws, 'unavailable': unavailable,
                       'opponents': n, 'coverage': coverage, 'dominant_axis': dominant, 'axes': axes,
                       'drawdown': ({'value': round(drawdown, 6), 'distance_from_high_pct': round(drawdown*100, 2),
                                     'position_pct': round(near_high*100, 2), 'last_close': stock.last_close_price,
                                     'high_52w': stock.high_52w,
                                     'note': (f'{ticker} is {drawdown:.1%} below its 52-week high. '
                                              'A strong 12-month return can coexist with a material drawdown.')}
                                    if drawdown is not None else None),
                       'benchmark': stock.benchmark, 'stock': stock.public_dict(),
                       'meaning': '',
                       'methodology': 'watcher-v1-valid-pairs',
                       'limitations': ['Performa 12M memakai perubahan market cap + yield sebagai proxy, bukan total return harga.',
                                       'Intrinsic value dari Sectors belum terverifikasi sebagai DCF.',
                                       'Payout lebih tinggi mengikuti aturan duel; tidak otomatis lebih sehat.']}
            profile['features'] = []
            for metric in METRICS:
                value = _comparable(stock, metric.key, False)
                profile['features'].append({'number': metric.number, 'segment': metric.segment,
                    'label': metric.label, 'raw': value.raw_value, 'baseline': value.baseline,
                    'value': value.value, 'basis': value.basis, 'direction': metric.direction})
            profiles[ticker] = profile

        ranked = sorted(
            (profile for profile in profiles.values() if profile['score'] is not None),
            key=lambda profile: (-profile['score'], profile['ticker']),
        )
        for rank, profile in enumerate(ranked, 1):
            profile['overall_rank'] = rank
            profile['overall_rank_total'] = len(ranked)
        for profile in profiles.values():
            profile.setdefault('overall_rank', None)
            profile.setdefault('overall_rank_total', len(ranked))

        for axis_name in AXES:
            axis_ranked = sorted(
                (
                    profile for profile in profiles.values()
                    if profile['axes'][axis_name]['score'] is not None
                ),
                key=lambda profile: (
                    # A stock that lost fewer head-to-head segment duels must
                    # sit above one that lost more. Wins, missing verdicts,
                    # then ticker make the ordering deterministic.
                    profile['axes'][axis_name]['losses'],
                    -profile['axes'][axis_name]['wins'],
                    profile['axes'][axis_name]['unavailable'],
                    profile['ticker'],
                ),
            )
            # Competition rank is defined by the actual head-to-head record:
            # zero losses = Top 1, one loss = Top 2, and so on. This prevents
            # an 85-1 segment record from being presented as Top 1 merely
            # because it has the best aggregate record in a cyclic cohort.
            for profile in axis_ranked:
                profile['axes'][axis_name]['rank'] = (
                    profile['axes'][axis_name]['losses'] + 1
                )
                profile['axes'][axis_name]['rank_total'] = len(axis_ranked)

            rank_groups = {}
            for row in axis_ranked:
                rank_groups.setdefault(row['axes'][axis_name]['rank'], []).append(row)

            for profile in axis_ranked:
                def neighbor(row):
                    axis = row['axes'][axis_name]
                    return {
                        'ticker': row['ticker'],
                        'rank': axis['rank'],
                        'wins': axis['wins'],
                        'losses': axis['losses'],
                    }
                rank = profile['axes'][axis_name]['rank']
                profile['axes'][axis_name]['ranks_above'] = [
                    neighbor(rank_groups[target_rank][0])
                    for target_rank in range(max(1, rank - 3), rank)
                    if target_rank in rank_groups
                ]
                profile['axes'][axis_name]['ranks_below'] = [
                    neighbor(rank_groups[target_rank][0])
                    for target_rank in range(rank + 1, rank + 4)
                    if target_rank in rank_groups
                ]
            for profile in profiles.values():
                profile['axes'][axis_name].setdefault('rank', None)
                profile['axes'][axis_name].setdefault('rank_total', len(axis_ranked))
                profile['axes'][axis_name].setdefault('ranks_above', [])
                profile['axes'][axis_name].setdefault('ranks_below', [])

        # Keep the interpretation as one paragraph, while grounding it in all
        # five original segment win counts and the segment rank requested by
        # the UI. This is descriptive only; it does not change any score.
        for profile in profiles.values():
            opponents = profile['opponents']
            axis_summary = '; '.join(
                f"{name} {profile['axes'][name]['wins']}/{opponents}"
                for name in AXES
            )
            dominant_names = (profile['dominant_axis'] or '').split(' / ')
            rank_parts = []
            for name in dominant_names:
                axis = profile['axes'].get(name)
                if axis and axis.get('rank') is not None:
                    rank_parts.append(
                        f"Top {axis['rank']} in {name} dari {axis['rank_total']} saham"
                    )
            dominant_text = (
                f"Segmen dominannya {profile['dominant_axis']}, dengan "
                + ' dan '.join(rank_parts)
                + '. '
                if rank_parts
                else f"Segmen dominannya {profile['dominant_axis'] or 'belum tersedia'}. "
            )
            drawdown = profile.get('drawdown')
            drawdown_text = (
                f"Posisi terakhir berada {drawdown['distance_from_high_pct']:.1f}% "
                "di bawah level tertinggi 52 minggu. "
                if drawdown else ''
            )
            profile['meaning'] = (
                f"{profile['ticker']} menang {profile['wins']} dari "
                f"{profile['wins'] + profile['losses']} duel berkeputusan, "
                f"dengan {profile['draws']} seri dan {profile['unavailable']} duel "
                f"tidak cukup data. Dari lima segmen, jumlah kemenangannya adalah "
                f"{axis_summary}. {dominant_text}Coverage verdict "
                f"{profile['coverage']:.0%}. {drawdown_text}Kemenangan segmen dapat "
                "tumpang tindih; batang bukan pembagian skor total."
            )

        return profiles

    def load(self):
        current = self.current()
        if not current:
            if self._cache_only_enabled() and not self._cache_only_attempted:
                self.load_partial_cache()
            return
        if not current or current.get('version') == self._version:
            return
        folder = self.root / 'snapshots' / current['version']
        sectors = read_csv(folder / 'subsectors.csv')
        stocks = {r['ticker']: apply_benchmark(snapshot_from_report(r['ticker'], json.loads(r['payload'])),
                                              sectors, self.client.settings.min_valid_peers)
                  for r in read_csv(folder / 'reports.csv')}
        profiles = {r['ticker']: json.loads(r['payload']) for r in read_csv(folder / 'profiles.csv')}
        if not profiles or any(
            profile.get('methodology') != 'watcher-v1-valid-pairs'
            or 'overall_rank' not in profile
            for profile in profiles.values()
        ):
            universe = read_csv(folder / 'universe.csv')
            cohort = [
                row['ticker'] for row in universe
                if str(row.get('cohort', '')).lower() in {'1', 'true', 'yes'}
                and row['ticker'] in stocks
            ]
            if len(cohort) < 2:
                cohort = list(stocks)
            profiles = self.build_profiles(stocks, cohort)
            # Local schema migration only: it consumes no provider credits and
            # preserves the raw reports/subsector snapshot unchanged.
            write_csv(folder / 'profiles.csv', [
                {
                    'ticker': ticker,
                    'score': profile['score'],
                    'dominant_axis': profile['dominant_axis'],
                    'payload': json.dumps(profile, allow_nan=False),
                }
                for ticker, profile in profiles.items()
            ])
        self._stocks, self._profiles, self._sectors = stocks, profiles, sectors
        self._manifest, self._version = current, current['version']

    def status(self):
        self.load()
        partial = bool(self._manifest.get('partial'))
        return {**self._manifest, 'ready': bool(self._version and self._stocks),
                'stale': True if partial else self.due(),
                'last_error': self.last_error, 'storage': 'CSV', 'interval_days': 7,
                'refresh_enabled': os.getenv('WEEKLY_REFRESH_ENABLED', 'true').strip().lower() in {'1', 'true', 'yes', 'on'},
                'weekly_credit_budget': int(os.getenv('WEEKLY_CREDIT_BUDGET', '550'))}

    def browse(self, query=''):
        self.load()
        rows = sorted(self._profiles.values(), key=lambda p: -(p['score'] if p['score'] is not None else -1))
        return {'meta': self.status(), 'items': [{k: p.get(k) for k in ('ticker','company_name','sector','sub_sector','score','overall_rank','overall_rank_total','dominant_axis','coverage','axes')}
                                               for p in rows if query.upper() in p['ticker'] or query.lower() in (p['company_name'] or '').lower()]}

    def detail(self, ticker):
        self.load()
        return {'meta': self.status(), 'profile': self._profiles.get(normalize_ticker(ticker))}

    def log_status(self):
        self.load()
        log.info('WEEKLY CSV | ready=%s | partial=%s | next=%s | refresh_enabled=%s | key configured=%s',
                 bool(self._version and self._stocks), bool(self._manifest.get('partial')),
                 self._manifest.get('next_refresh_at', 'first run'),
                 os.getenv('WEEKLY_REFRESH_ENABLED', 'true'), bool(self.client.settings.api_key))
        for r in self._sectors:
            log.info('CACHED SUBSECTOR %s / %s | median PE=%s | companies=%s | fetched=%s',
                     r['sector'], r['sub_sector'], r['filtered_median_pe'], r['total_companies'], r['fetched_at'])

    async def schedule(self):
        while True:
            if self.due() and utcnow() >= self._next_retry:
                try:
                    await asyncio.to_thread(self.refresh)
                except Exception as exc:
                    self.last_error = str(exc)
                    log.error('Weekly refresh incomplete; previous CSV retained: %s', exc)
                    self._next_retry = utcnow()+timedelta(hours=6)
            await asyncio.sleep(60)
