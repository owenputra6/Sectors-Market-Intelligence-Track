from __future__ import annotations

import asyncio
import json
import ssl
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.config import Settings
from app.sectors_client import SectorsClient


class CacheTests(unittest.TestCase):
    def make_client(self, cache_dir: Path) -> SectorsClient:
        settings = Settings(
            api_key="",
            base_url="https://api.sectors.app/v2",
            cache_dir=cache_dir,
            cache_ttl_seconds=86400,
            request_timeout_seconds=5,
            max_retries=0,
            allow_stale_if_error=True,
            cors_origins=("http://localhost:5173",),
            report_sections=("overview", "valuation", "financials", "dividend", "peers"),
            max_missing_feature_rate=0.35,
            min_valid_peers=5,
        )
        return SectorsClient(settings)

    def test_fresh_cache_serves_without_api_key_or_credits(self):
        with tempfile.TemporaryDirectory() as directory:
            client = self.make_client(Path(directory))
            path, params = client._request_identity("BBCA")
            client._write_cache(
                path,
                params,
                {"symbol": "BBCA.JK", "overview": {}, "valuation": {}},
            )

            status = client.cache_status("BBCA")
            self.assertEqual(status["state"], "fresh")
            self.assertEqual(status["estimated_refresh_credits"], 0)

            result = asyncio.run(client.fetch_company_report("BBCA"))
            self.assertEqual(result.source, "cache")
            self.assertEqual(result.estimated_credits, 0)
            self.assertEqual(result.payload["symbol"], "BBCA.JK")

    def test_uncached_ticker_estimates_five_credits(self):
        with tempfile.TemporaryDirectory() as directory:
            client = self.make_client(Path(directory))
            status = client.cache_status("PANI")
            self.assertEqual(status["state"], "missing")
            self.assertEqual(status["estimated_refresh_credits"], 5)

    def test_live_request_uses_explicit_certifi_ssl_context(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def read(self):
                return json.dumps(
                    {"symbol": "BBCA.JK", "overview": {"company_name": "BCA"}}
                ).encode("utf-8")

        with tempfile.TemporaryDirectory() as directory:
            client = self.make_client(Path(directory))
            self.assertIsInstance(client.ssl_context, ssl.SSLContext)
            path, params = client._request_identity("BBCA")

            with patch("app.sectors_client.urlopen", return_value=FakeResponse()) as call:
                result = client._request_report(path, params)

            self.assertEqual(result["symbol"], "BBCA.JK")
            self.assertIs(call.call_args.kwargs["context"], client.ssl_context)


if __name__ == "__main__":
    unittest.main()
