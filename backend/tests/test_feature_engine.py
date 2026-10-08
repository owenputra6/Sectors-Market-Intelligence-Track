from __future__ import annotations

import unittest

from app.feature_engine import StockSnapshot, run_duel, snapshot_from_report


def make_snapshot(**overrides):
    base = dict(
        ticker="TEST",
        sub_sector="Example",
        last_close_price=100.0,
        pe_ttm=10.0,
        pb_mrq=1.0,
        intrinsic_value=120.0,
        revenue_growth=0.10,
        earnings_growth=0.10,
        quarterly_earnings_growth=0.10,
        roe=0.15,
        roa=0.07,
        net_margin=0.12,
        market_cap_change_12m=0.10,
        high_52w=120.0,
        yield_ttm=0.02,
        yield_5y=0.02,
        payout_ratio=0.40,
        peer_medians={
            "pe_ttm": 10.0,
            "pb_mrq": 1.0,
            "roe": 0.10,
            "roa": 0.05,
            "net_margin": 0.10,
            "market_cap_change_12m": 0.05,
        },
        peer_counts={
            "pe_ttm": 10,
            "pb_mrq": 10,
            "roe": 10,
            "roa": 10,
            "net_margin": 10,
            "market_cap_change_12m": 10,
        },
    )
    base.update(overrides)
    return StockSnapshot(**base)


class FeatureEngineTests(unittest.TestCase):
    def test_pani_vs_bbca_matches_document_segment_result(self):
        pani = make_snapshot(
            ticker="PANI",
            sub_sector="Properties & Real Estate",
            last_close_price=5075,
            pe_ttm=80.14,
            pb_mrq=3.17,
            intrinsic_value=-4503,
            revenue_growth=0.5265,
            earnings_growth=0.8389,
            quarterly_earnings_growth=3.6151,
            roe=0.0362,
            roa=None,
            net_margin=0.4934,
            market_cap_change_12m=-0.6522,
            high_52w=16100,
            yield_ttm=0.001,
            yield_5y=0.0001,
            payout_ratio=0.0354,
            peer_medians={
                "pe_ttm": 6.57,
                "pb_mrq": 0.87,
                "roe": 0.0915,
                "roa": None,
                "net_margin": 0.3520,
                "market_cap_change_12m": -0.3045,
            },
        )
        bbca = make_snapshot(
            ticker="BBCA",
            sub_sector="Banks",
            last_close_price=6300,
            pe_ttm=13.36,
            pb_mrq=2.84,
            intrinsic_value=9987,
            revenue_growth=0.0342,
            earnings_growth=0.0493,
            quarterly_earnings_growth=-0.0014,
            roe=0.2043,
            roa=0.0363,
            net_margin=0.6362,
            market_cap_change_12m=-0.2250,
            high_52w=8750,
            yield_ttm=0.0605,
            yield_5y=0.0283,
            payout_ratio=0.8015,
            peer_medians={
                "pe_ttm": 9.38,
                "pb_mrq": 0.79,
                "roe": 0.1712,
                "roa": 0.0199,
                "net_margin": 0.3536,
                "market_cap_change_12m": -0.1864,
            },
        )

        result = run_duel(pani, bbca)
        segment_winners = {row["segment"]: row["winner"] for row in result["segments"]}

        self.assertEqual(segment_winners["Valuation"], "BBCA")
        self.assertEqual(segment_winners["Growth"], "PANI")
        self.assertEqual(segment_winners["Financial"], "BBCA")
        self.assertEqual(segment_winners["Performance"], "BBCA")
        self.assertEqual(segment_winners["Dividend"], "BBCA")
        self.assertEqual(result["verdict"]["winner"], "BBCA")
        self.assertEqual(result["verdict"]["segment_wins_a"], 1)
        self.assertEqual(result["verdict"]["segment_wins_b"], 4)
        self.assertEqual(result["verdict"]["valid_features"], 13)
        self.assertAlmostEqual(
            result["verdict"]["feature_point_share_a"]
            + result["verdict"]["feature_point_share_b"],
            100,
            places=2,
        )
        for segment in result["segments"]:
            if segment["valid_features"]:
                self.assertAlmostEqual(
                    segment["point_share_a"] + segment["point_share_b"],
                    100,
                    places=2,
                )

        feature_8 = next(row for row in result["features"] if row["number"] == 8)
        self.assertEqual(feature_8["winner"], "draw")
        self.assertEqual(feature_8["reason"], "missing_data")

        feature_3 = next(row for row in result["features"] if row["number"] == 3)
        self.assertEqual(feature_3["winner"], "BBCA")
        self.assertEqual(feature_3["reason"], "invalid_value")
        valuation = next(
            row for row in result["segments"] if row["segment"] == "Valuation"
        )
        self.assertEqual(valuation["valid_features"], 2)
        self.assertEqual(valuation["missing_features"], 1)

    def test_same_subsector_uses_raw_values(self):
        a = make_snapshot(
            ticker="AAAA",
            sub_sector="Banks",
            pe_ttm=8.0,
            peer_medians={
                **make_snapshot().peer_medians,
                "pe_ttm": 4.0,
            },
        )
        b = make_snapshot(
            ticker="BBBB",
            sub_sector="Banks",
            pe_ttm=10.0,
            peer_medians={
                **make_snapshot().peer_medians,
                "pe_ttm": 20.0,
            },
        )
        result = run_duel(a, b)
        pe = next(row for row in result["features"] if row["number"] == 1)
        self.assertEqual(pe["comparison_basis"], "raw")
        self.assertEqual(pe["winner"], "AAAA")
        self.assertEqual(pe["value_a"], 8.0)
        self.assertEqual(pe["value_b"], 10.0)

    def test_continuous_share_uses_margin_without_changing_segment_winner(self):
        a = make_snapshot(
            ticker="AAAA",
            sub_sector="Banks",
            pe_ttm=8.0,
            pb_mrq=1.0,
            last_close_price=100.0,
            intrinsic_value=100.0,
        )
        b = make_snapshot(
            ticker="BBBB",
            sub_sector="Banks",
            pe_ttm=10.0,
            pb_mrq=2.0,
            last_close_price=100.0,
            intrinsic_value=200.0,
        )
        result = run_duel(a, b)
        valuation = next(
            row for row in result["segments"] if row["segment"] == "Valuation"
        )
        self.assertEqual(valuation["winner"], "AAAA")
        self.assertNotEqual(valuation["point_share_a"], 66.67)
        self.assertAlmostEqual(
            valuation["point_share_a"] + valuation["point_share_b"], 100, places=2
        )

    def test_missing_feature_is_excluded_from_segment_percentage(self):
        a = make_snapshot(
            ticker="AAAA",
            sub_sector="Banks",
            pe_ttm=8.0,
            pb_mrq=1.0,
            intrinsic_value=None,
        )
        b = make_snapshot(
            ticker="BBBB",
            sub_sector="Banks",
            pe_ttm=10.0,
            pb_mrq=2.0,
            intrinsic_value=None,
        )
        result = run_duel(a, b)
        valuation = next(
            row for row in result["segments"] if row["segment"] == "Valuation"
        )

        self.assertEqual(valuation["valid_features"], 2)
        self.assertEqual(valuation["missing_features"], 1)
        self.assertEqual(valuation["wins_a"], 2)
        self.assertEqual(valuation["point_share_a"], 100.0)
        self.assertEqual(valuation["point_share_b"], 0.0)

    def test_excessive_missing_data_suppresses_verdict(self):
        a = make_snapshot(ticker="AAAA")
        b = make_snapshot(
            ticker="BBBB",
            pe_ttm=None,
            pb_mrq=None,
            intrinsic_value=None,
            revenue_growth=None,
            earnings_growth=None,
            quarterly_earnings_growth=None,
            roe=None,
            roa=None,
            net_margin=None,
        )
        result = run_duel(a, b)
        self.assertFalse(result["verdict"]["available"])
        self.assertEqual(result["verdict"]["winner"], "unavailable")
        self.assertGreater(
            next(row for row in result["segments"] if row["segment"] == "Valuation")["missing_features"],
            0,
        )

    def test_snapshot_uses_consistent_self_and_peer_formulas(self):
        report = {
            "company_name": "Example Tbk",
            "overview": {
                "sector": "Financials",
                "sub_sector": "Banks",
                "listing_board": "Main",
                "last_close_price": 100,
                "latest_close_date": "2026-09-24",
                "all_time_price": {"52_w_high": {"2026-01-01": 125}},
            },
            "valuation": {"intrinsic_value": 150},
            "financials": {
                "historical_financials": [
                    {"year": 2024, "revenue": 1000, "earnings": 100},
                    {"year": 2025, "revenue": 1100, "earnings": 120},
                ],
                "yoy_quarter_earnings_growth": 0.25,
            },
            "dividend": {
                "yield_ttm": 0.02,
                "dividend_yield_avg": {"avg_yield": 0.015},
                "payout_ratio": 0.4,
            },
            "peers": [
                {
                    "peers_data": {
                        "group_name": {"sector": "Financials", "sub_sector": "Banks"},
                        "companies": [
                            {
                                "symbol": "TEST.JK",
                                "group": ["self"],
                                "pe_ttm": 10,
                                "pb_mrq": 1.5,
                                "net_income": 120,
                                "total_equity": 600,
                                "total_assets": 3000,
                                "total_revenue": 1100,
                                "yearly_mcap_chg": 0.1,
                            },
                            {
                                "symbol": "PEER.JK",
                                "group": ["sub_sector"],
                                "pe_ttm": 12,
                                "pb_mrq": 1.2,
                                "net_income": 80,
                                "total_equity": 500,
                                "total_assets": 2000,
                                "total_revenue": 800,
                                "yearly_mcap_chg": 0.05,
                            },
                        ],
                    }
                }
            ],
        }
        snapshot = snapshot_from_report("TEST", report, min_valid_peers=1)
        self.assertAlmostEqual(snapshot.roe, 0.2)
        self.assertAlmostEqual(snapshot.roa, 0.04)
        self.assertAlmostEqual(snapshot.net_margin, 120 / 1100)
        self.assertAlmostEqual(snapshot.peer_medians["roe"], 0.16)
        self.assertAlmostEqual(snapshot.revenue_growth, 0.1)
        self.assertAlmostEqual(snapshot.earnings_growth, 0.2)


if __name__ == "__main__":
    unittest.main()
