from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.feature_engine import StockSnapshot
from app.main import app, weekly
from app.sectors_client import FetchResult


def snapshot(ticker: str, subsector: str, advantage: float) -> StockSnapshot:
    return StockSnapshot(
        ticker=ticker,
        company_name=f"{ticker} Example Tbk",
        sector="Example Sector",
        sub_sector=subsector,
        listing_board="Main",
        as_of="2026-09-25",
        last_close_price=100,
        market_cap=1_000_000_000_000,
        market_cap_rank=10,
        pe_ttm=10 - advantage,
        pb_mrq=1.5 - advantage / 10,
        intrinsic_value=130 + advantage,
        revenue_growth=0.10 + advantage / 10,
        earnings_growth=0.12 + advantage / 10,
        quarterly_earnings_growth=0.08 + advantage / 10,
        roe=0.15 + advantage / 10,
        roa=0.07 + advantage / 20,
        net_margin=0.18 + advantage / 10,
        market_cap_change_12m=0.10 + advantage / 10,
        high_52w=120,
        yield_ttm=0.02 + advantage / 100,
        yield_5y=0.018 + advantage / 100,
        payout_ratio=0.40 + advantage / 10,
        peer_medians={
            "pe_ttm": 10,
            "pb_mrq": 1.5,
            "roe": 0.12,
            "roa": 0.05,
            "net_margin": 0.15,
            "market_cap_change_12m": 0.05,
        },
        peer_counts={key: 9 for key in (
            "pe_ttm", "pb_mrq", "roe", "roa", "net_margin", "market_cap_change_12m"
        )},
    )


class ApiContractTests(unittest.TestCase):
    def setUp(self):
        self.http = TestClient(app)

    def test_any_local_flutter_web_port_passes_cors_preflight(self):
        response = self.http.options(
            "/api/v1/duels",
            headers={
                "Origin": "http://localhost:54321",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["access-control-allow-origin"],
            "http://localhost:54321",
        )

    def test_duel_contract_contains_market_intelligence(self):
        stocks = {"AAAA": snapshot("AAAA", "Banks", 0.4), "BBBB": snapshot("BBBB", "Energy", 0.0)}
        with patch("app.main.weekly.load"), patch("app.main.weekly._stocks", stocks), patch(
            "app.main.weekly.status", return_value={"ready": True}
        ):
            response = self.http.post(
                "/api/v1/duels",
                json={
                    "ticker_a": "AAAA",
                    "ticker_b": "BBBB",
                    "max_new_credits": 10,
                },
            )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["features"]), 15)
        self.assertEqual(len(payload["segments"]), 5)
        self.assertIn("headline", payload["market_intelligence"])
        self.assertEqual(len(payload["market_intelligence"]["segment_drivers"]), 5)
        self.assertEqual(payload["meta"]["estimated_new_credits_upper_bound"], 0)

    def test_browse_exposes_sector_and_segment_scores_for_v4_routes(self):
        profiles = {
            "AAAA": {
                "ticker": "AAAA",
                "company_name": "AAAA Example Tbk",
                "sector": "Financials",
                "sub_sector": "Banks",
                "score": 75.0,
                "overall_rank": 1,
                "overall_rank_total": 1,
                "dominant_axis": "Financial",
                "coverage": 1.0,
                "axes": {"Financial": {"score": 80.0}},
            }
        }
        with patch.object(weekly, "_profiles", profiles), patch.object(
            weekly, "load"
        ), patch.object(weekly, "status", return_value={"ready": True}):
            response = self.http.get("/api/v1/stocks")
        self.assertEqual(response.status_code, 200)
        row = response.json()["items"][0]
        self.assertEqual(row["sector"], "Financials")
        self.assertEqual(row["axes"]["Financial"]["score"], 80.0)


if __name__ == "__main__":
    unittest.main()
