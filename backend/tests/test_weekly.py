import copy
import json
import os
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.config import Settings
from app.feature_engine import snapshot_from_report, run_duel
from app.sectors_client import SectorsClient
from app.weekly import WeeklyStore, apply_benchmark, read_csv, write_csv, utcnow


def report(ticker, sector, subsector, pe):
    rows = [{'symbol': ticker, 'group': ['self'], 'pe_ttm': pe, 'pb_mrq': 2,
             'net_income': 20, 'total_equity': 100, 'total_assets': 200, 'total_revenue': 80,
             'yearly_mcap_chg': .2}]
    rows += [dict(rows[0], symbol=f'P{i:03}', group=[], pe_ttm=10+i) for i in range(6)]
    return {'symbol': ticker+'.JK', 'company_name': ticker+' Example',
            'overview': {'sector': sector, 'sub_sector': subsector, 'last_close_price': 100,
                         'all_time_price': {'52_w_high': {'2026-09-01': 120}}},
            'valuation': {'intrinsic_value': 140},
            'financials': {'historical_financials': [{'year': 2024, 'revenue': 100, 'earnings': 10},
                                                    {'year': 2025, 'revenue': 110, 'earnings': 12}],
                           'yoy_quarter_earnings_growth': .1},
            'dividend': {'yield_ttm': .03, 'dividend_yield_avg': {'period': 5, 'avg_yield': .02}, 'payout_ratio': .4},
            'peers': [{'peers_data': {'group_name': {'sector': sector, 'sub_sector': subsector}, 'companies': rows}}]}


class WeeklyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.settings = Settings(api_key='test-only', base_url='https://api.sectors.app/v2',
            cache_dir=Path(self.temp.name)/'cache', cache_ttl_seconds=604800,
            request_timeout_seconds=1, max_retries=0, allow_stale_if_error=True, cors_origins=(),
            report_sections=('overview','valuation','financials','dividend','peers'),
            max_missing_feature_rate=.35, min_valid_peers=5)
        self.store = WeeklyStore(SectorsClient(self.settings))
        self.calls = []
        self.env = patch.dict(os.environ, {'COHORT_INDEX': '', 'COHORT_SIZE': '2', 'TRACKED_TICKERS': '', 'WEEKLY_REFRESH_ENABLED': 'false'})
        self.env.start(); self.addCleanup(self.env.stop)

    def request(self, path, params, cost):
        self.calls.append((path, params, cost))
        if path == '/subsectors/':
            return [{'sector': 'financials', 'subsector': 'banks'}, {'sector': 'properties-real-estate', 'subsector': 'properties-real-estate'}]
        if path.startswith('/subsector/report/'):
            bank = '/banks/' in path
            return {'sector': 'Financials' if bank else 'Properties & Real Estate',
                    'sub_sector': 'Banks' if bank else 'Properties & Real Estate',
                    'statistics': {'total_companies': 48 if bank else 90,
                                   'filtered_median_pe': 9.38 if bank else 6.57}}
        if path == '/companies/':
            if params['offset'] == '0':
                return {'results': [{'symbol': 'BBCA.JK', 'company_name': 'Example bank'}],
                        'pagination': {'has_next': True, 'next_offset': 1}}
            return {'results': [{'symbol': 'PANI.JK', 'company_name': 'Example property'}],
                    'pagination': {'has_next': False}}
        if '/BBCA/' in path:
            return report('BBCA', 'Financials', 'Banks', 13.36)
        return report('PANI', 'Properties & Real Estate', 'Properties & Real Estate', 80.14)

    def seed(self):
        with patch.object(self.store, 'request', side_effect=self.request): self.store.refresh()

    def test_real_contract_pagination_subsector_pe_and_csv_roundtrip(self):
        self.seed()
        a, b = self.store._stocks['BBCA'], self.store._stocks['PANI']
        feature = run_duel(a,b)['features'][0]
        self.assertAlmostEqual(feature['value_a'], 13.36/9.38)
        self.assertAlmostEqual(feature['value_b'], 80.14/6.57)
        self.assertEqual(a.benchmark['valid_pe_count'], None)
        self.assertEqual(a.benchmark['total_companies'], 48)
        self.assertTrue(any(c[1].get('offset') == '1' for c in self.calls))
        self.assertFalse(list(self.store.root.parent.rglob('*.json')))
        other = WeeklyStore(SectorsClient(self.settings)); other.load()
        self.assertEqual(other._stocks['BBCA'].pe_ttm, 13.36)
        self.assertEqual(other.detail('bbca')['profile']['opponents'], 1)
        self.assertNotIn('shift', other.detail('BBCA')['profile'])
        self.assertEqual(len(other.detail('BBCA')['profile']['features']), 15)
        profile = other.detail('BBCA')['profile']
        self.assertEqual(profile['overall_rank_total'], 2)
        self.assertIn('rank', profile['axes']['Valuation'])
        self.assertEqual(profile['axes']['Valuation']['rank'], 1)
        self.assertEqual(profile['axes']['Valuation']['ranks_below'][0]['ticker'], 'PANI')
        pani = other.detail('PANI')['profile']
        self.assertEqual(pani['axes']['Valuation']['rank'], 2)
        self.assertEqual(pani['axes']['Valuation']['ranks_above'][0]['ticker'], 'BBCA')
        for axis in profile['axes'].values():
            self.assertEqual(axis['score'], round(100 * axis['wins'] / profile['opponents'], 2))
            self.assertEqual(axis['rank'], axis['losses'] + 1)
        for axis in pani['axes'].values():
            self.assertEqual(axis['rank'], axis['losses'] + 1)
        self.assertIsNotNone(profile['drawdown'])
        self.assertIn('batang bukan pembagian skor total', profile['meaning'])
        for axis_name in ('Valuation', 'Growth', 'Financial', 'Performance', 'Dividend'):
            self.assertIn(axis_name, profile['meaning'])
        self.assertIn('Top 1 in Valuation', profile['meaning'])
        self.assertNotIn('30-day', profile['meaning'])
        self.assertNotIn('insights', profile)
        self.assertIn('overall_rank', other.browse()['items'][0])

    def test_second_refresh_and_browse_do_not_call_provider(self):
        self.seed()
        count = len(self.calls)
        with patch.object(self.store, 'request', side_effect=AssertionError('API MUST NOT RUN')):
            self.store.refresh(); self.store.browse(); self.store.detail('BBCA')
        self.assertEqual(len(self.calls), count)

    def test_default_index_cohort_uses_structured_companies_filter(self):
        with patch.dict(os.environ, {'COHORT_INDEX': 'KOMPAS100'}):
            self.seed()
        company_calls = [params for path, params, _ in self.calls if path == '/companies/']
        self.assertTrue(company_calls)
        self.assertEqual(company_calls[0]['where'], "indices in ['KOMPAS100']")
        self.assertEqual(self.store.current()['cohort_name'], 'KOMPAS100')

    def test_sector_cohort_uses_api_filter_and_size(self):
        with patch.dict(os.environ, {
            'COHORT_INDEX': '', 'COHORT_SECTOR': 'Financials',
            'COHORT_SUBSECTOR': 'Banks', 'COHORT_SIZE': '2',
        }):
            self.seed()
        params = next(params for path, params, _ in self.calls if path == '/companies/')
        self.assertEqual(params['where'], "sector = 'Financials' and sub_sector = 'Banks'")
        self.assertEqual(self.store.current()['cohort_name'], 'Financials · Banks · top 2')

    def test_multi_sector_refresh_keeps_every_returned_company(self):
        with patch.dict(os.environ, {
            'COHORT_INDEX': '',
            'COHORT_SECTORS': 'Financials,Properties & Real Estate',
            'COHORT_SECTOR': '',
            'COHORT_SUBSECTOR': '',
            'COHORT_SIZE': '0',
        }):
            self.seed()
        params = next(params for path, params, _ in self.calls if path == '/companies/')
        self.assertEqual(
            params['where'],
            "sector in ['Financials','Properties & Real Estate']",
        )
        self.assertEqual(self.store.current()['cohort_size'], '2')

    def test_refresh_logs_exact_subsector_pe_evidence(self):
        with self.assertLogs('uvicorn.error', level='INFO') as captured:
            self.seed()
        output = '\n'.join(captured.output)
        self.assertIn('SUBSECTOR Financials / Banks | median PE=9.38', output)
        self.assertIn('STOCK BBCA | Financials / Banks | PE=13.36 / subsector median=9.38', output)
        self.assertIn('CSV SNAPSHOT PUBLISHED', output)

    def test_wrong_subsector_cannot_fall_back_to_broad_sector(self):
        raw = report('BBCA', 'Financials', 'Banks', 13.36)
        raw['peers'][0]['peers_data']['group_name']['sub_sector'] = 'Insurance'
        stock = snapshot_from_report('BBCA', raw)
        self.assertIsNone(stock.pe_ttm)
        apply_benchmark(stock, [{'sector':'Financials', 'sub_sector':'Insurance', 'filtered_median_pe':1, 'total_companies':10}])
        self.assertIsNone(stock.peer_medians['pe_ttm'])

    def test_same_subsector_uses_raw_pe(self):
        a = snapshot_from_report('AAAA', report('AAAA','Financials','Banks',12))
        b = snapshot_from_report('BBBB', report('BBBB','Financials','Banks',15))
        self.assertEqual(run_duel(a,b)['features'][0]['value_a'], 12)

    def test_nonpositive_pe_not_a_cheap_win(self):
        a = snapshot_from_report('AAAA', report('AAAA','Financials','Banks',-1))
        b = snapshot_from_report('BBBB', report('BBBB','Financials','Banks',15))
        self.assertIsNone(run_duel(a,b)['features'][0]['value_a'])

    def test_failed_refresh_retains_published_snapshot(self):
        self.seed(); before = self.store.current()['version']
        with patch.object(self.store, 'due', return_value=True), patch.object(self.store, 'cached_request', side_effect=RuntimeError('offline')):
            with self.assertRaises(RuntimeError): self.store.refresh()
        self.assertEqual(self.store.current()['version'], before)
        self.assertEqual(len(self.store.browse()['items']), 2)

    def test_budget_is_reserved_before_any_network_request(self):
        with patch.dict(os.environ, {'WEEKLY_CREDIT_BUDGET':'1'}), patch('app.weekly.urlopen', side_effect=OSError('offline')) as net:
            with self.assertRaises(RuntimeError): self.store.request('/subsectors/', {}, 1)
            with self.assertRaisesRegex(RuntimeError, 'budget'): self.store.request('/subsectors/', {}, 1)
        self.assertEqual(net.call_count, 1)
        self.assertEqual(read_csv(self.store.root/'credits.csv')[0]['cost'], '1')

    def test_seven_day_due_survives_restart(self):
        self.seed(); current = self.store.current()
        current['next_refresh_at'] = (utcnow()-timedelta(seconds=1)).isoformat()
        write_csv(self.store.root/'current.csv', [current])
        self.assertTrue(WeeklyStore(SectorsClient(self.settings)).due())

    def test_api_uses_published_csv_and_cors(self):
        self.seed()
        from app.main import app
        with patch('app.main.weekly', self.store), patch('app.weekly.urlopen', side_effect=AssertionError('No live calls')):
            http = TestClient(app)
            self.assertEqual(http.get('/api/v1/stocks').status_code,200)
            self.assertEqual(http.get('/api/v1/stocks/BBCA').json()['profile']['benchmark']['pe_median'],9.38)
            self.assertEqual(http.get('/api/v1/stocks/ZZZZ').status_code,404)
            self.assertEqual(len(http.get('/api/v1/sectors').json()['items']),2)
            duel=http.post('/api/v1/duels',json={'ticker_a':'PANI','ticker_b':'BBCA'})
            self.assertEqual(duel.status_code,200)
            self.assertEqual(duel.json()['meta']['estimated_new_credits_upper_bound'],0)
            self.assertEqual(len(duel.json()['features']),15)
            self.assertEqual(http.post('/api/v1/duels',json={'ticker_a':'PANI','ticker_b':'BBCA','force_refresh':True}).status_code,409)
            self.assertEqual(http.options('/api/v1/stocks',headers={'Origin':'http://localhost:5173','Access-Control-Request-Method':'GET'}).status_code,200)
