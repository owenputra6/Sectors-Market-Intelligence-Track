from __future__ import annotations

import asyncio
import csv
import hashlib
import json
import os
import random
import ssl
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import certifi

from .config import Settings


class SectorsClientError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class FetchResult:
    ticker: str
    payload: dict[str, Any]
    source: str
    fetched_at: str
    expires_at: str
    estimated_credits: int
    warning: str | None = None


def normalize_ticker(value: str) -> str:
    ticker = str(value).strip().upper()
    if ticker.endswith(".JK"):
        ticker = ticker[:-3]
    return ticker


class SectorsClient:
    """Company Report client with cache-first semantics and request coalescing."""

    CACHE_SCHEMA = 1

    def __init__(self, settings: Settings):
        self.settings = settings
        self.settings.cache_dir.mkdir(parents=True, exist_ok=True)
        # Use an explicit, maintained CA bundle. On some Windows/Anaconda
        # installations, ssl.create_default_context() tries to parse a corrupt
        # certificate from the Windows store and fails with ASN1: NOT_ENOUGH_DATA
        # before the HTTP request is ever sent.
        self.ssl_context = ssl.create_default_context(cafile=certifi.where())
        self._locks: dict[str, asyncio.Lock] = {}
        self._locks_guard = asyncio.Lock()

    @property
    def section_cost(self) -> int:
        return len(self.settings.report_sections)

    def _request_identity(self, ticker: str) -> tuple[str, dict[str, str]]:
        path = f"/company/report/{normalize_ticker(ticker)}/"
        params = {"sections": ",".join(self.settings.report_sections)}
        return path, params

    def _cache_key(self, path: str, params: dict[str, str]) -> str:
        packed = json.dumps(
            [self.CACHE_SCHEMA, self.settings.base_url, path, params],
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(packed.encode("utf-8")).hexdigest()

    def _cache_path(self, path: str, params: dict[str, str]) -> Path:
        return self.settings.cache_dir / f"{self._cache_key(path, params)}.csv"

    def _read_cache(
        self, path: str, params: dict[str, str]
    ) -> tuple[str, dict[str, Any] | None]:
        file = self._cache_path(path, params)
        if not file.is_file():
            return "missing", None
        try:
            with file.open(encoding="utf-8", newline="") as handle:
                envelope = next(csv.DictReader(handle))
            envelope["schema"] = int(envelope["schema"])
            envelope["payload"] = json.loads(envelope["payload"])
            if envelope.get("schema") != self.CACHE_SCHEMA:
                return "invalid", None
            if envelope.get("request_key") != self._cache_key(path, params):
                return "invalid", None
            payload = envelope.get("payload")
            encoded = json.dumps(
                payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
            if envelope.get("payload_sha256") != hashlib.sha256(encoded).hexdigest():
                return "invalid", None
            fetched = datetime.fromisoformat(envelope["fetched_at"])
            age = (datetime.now(timezone.utc) - fetched).total_seconds()
            state = "fresh" if age <= self.settings.cache_ttl_seconds else "stale"
            return state, envelope
        except (OSError, ValueError, TypeError, KeyError, StopIteration, csv.Error, json.JSONDecodeError):
            return "invalid", None

    def _write_cache(
        self, path: str, params: dict[str, str], payload: dict[str, Any]
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        encoded = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        envelope = {
            "schema": self.CACHE_SCHEMA,
            "request_key": self._cache_key(path, params),
            "fetched_at": now.isoformat(),
            "expires_at": (
                now + timedelta(seconds=self.settings.cache_ttl_seconds)
            ).isoformat(),
            "payload_sha256": hashlib.sha256(encoded).hexdigest(),
            "payload": payload,
        }
        target = self._cache_path(path, params)
        fd, temp_name = tempfile.mkstemp(
            prefix=".tmp-sectors-", suffix=".csv", dir=self.settings.cache_dir
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(envelope))
                writer.writeheader()
                writer.writerow({**envelope, "payload": json.dumps(payload, ensure_ascii=False, allow_nan=False)})
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, target)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
        return envelope

    async def _lock_for(self, key: str) -> asyncio.Lock:
        async with self._locks_guard:
            return self._locks.setdefault(key, asyncio.Lock())

    def cache_status(self, ticker: str) -> dict[str, Any]:
        ticker = normalize_ticker(ticker)
        path, params = self._request_identity(ticker)
        state, envelope = self._read_cache(path, params)
        return {
            "ticker": ticker,
            "state": state,
            "fetched_at": envelope.get("fetched_at") if envelope else None,
            "expires_at": envelope.get("expires_at") if envelope else None,
            "sections": list(self.settings.report_sections),
            "estimated_refresh_credits": 0 if state == "fresh" else self.section_cost,
        }

    async def fetch_company_report(
        self, ticker: str, *, force_refresh: bool = False
    ) -> FetchResult:
        ticker = normalize_ticker(ticker)
        path, params = self._request_identity(ticker)
        key = self._cache_key(path, params)
        lock = await self._lock_for(key)
        async with lock:
            state, envelope = self._read_cache(path, params)
            if state == "fresh" and not force_refresh and envelope:
                return FetchResult(
                    ticker=ticker,
                    payload=envelope["payload"],
                    source="cache",
                    fetched_at=envelope["fetched_at"],
                    expires_at=envelope["expires_at"],
                    estimated_credits=0,
                )

            if not self.settings.api_key:
                if envelope and self.settings.allow_stale_if_error:
                    return FetchResult(
                        ticker=ticker,
                        payload=envelope["payload"],
                        source="stale_cache",
                        fetched_at=envelope["fetched_at"],
                        expires_at=envelope["expires_at"],
                        estimated_credits=0,
                        warning="SECTORS_API_KEY is missing; stale cache was served.",
                    )
                raise SectorsClientError(
                    "SECTORS_API_KEY is not configured and no usable cache exists.",
                    status_code=503,
                )

            try:
                payload = await asyncio.to_thread(self._request_report, path, params)
                fresh = self._write_cache(path, params, payload)
                return FetchResult(
                    ticker=ticker,
                    payload=payload,
                    source="api",
                    fetched_at=fresh["fetched_at"],
                    expires_at=fresh["expires_at"],
                    estimated_credits=self.section_cost,
                )
            except SectorsClientError as exc:
                if envelope and self.settings.allow_stale_if_error:
                    return FetchResult(
                        ticker=ticker,
                        payload=envelope["payload"],
                        source="stale_cache_after_error",
                        fetched_at=envelope["fetched_at"],
                        expires_at=envelope["expires_at"],
                        estimated_credits=self.section_cost,
                        warning=f"Live refresh failed; stale cache served: {exc}",
                    )
                raise

    def _request_report(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        query = urlencode(params)
        url = f"{self.settings.base_url}{path}?{query}"
        request = Request(
            url,
            headers={
                "Authorization": self.settings.api_key,
                "Accept": "application/json",
                "User-Agent": "sectors-stock-duel-backend/2.0 (+https://docs.sectors.app)",
            },
        )
        last_error: Exception | None = None
        attempts = self.settings.max_retries + 1
        for attempt in range(attempts):
            try:
                with urlopen(
                    request,
                    timeout=self.settings.request_timeout_seconds,
                    context=self.ssl_context,
                ) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                if not isinstance(payload, dict):
                    raise SectorsClientError("Sectors returned a non-object response.")
                if payload.get("error"):
                    raise SectorsClientError(
                        f"Sectors API error: {payload.get('error')}", status_code=502
                    )
                expected_ticker = normalize_ticker(path.rstrip("/").split("/")[-1])
                returned_ticker = normalize_ticker(payload.get("symbol", ""))
                if returned_ticker and returned_ticker != expected_ticker:
                    raise SectorsClientError(
                        "Sectors returned a report for a different ticker.",
                        status_code=502,
                    )
                if not any(
                    section in payload for section in self.settings.report_sections
                ):
                    raise SectorsClientError(
                        "Sectors response did not contain any requested report section.",
                        status_code=502,
                    )
                return payload
            except HTTPError as exc:
                body = exc.read(2_000).decode("utf-8", errors="replace")
                safe_body = body.replace(self.settings.api_key, "[REDACTED]")
                if exc.code in {401, 403, 404} or attempt + 1 >= attempts:
                    raise SectorsClientError(
                        f"Sectors API HTTP {exc.code}: {safe_body}",
                        status_code=exc.code,
                    ) from exc
                last_error = exc
            except (
                URLError,
                TimeoutError,
                ssl.SSLError,
                ValueError,
                json.JSONDecodeError,
            ) as exc:
                last_error = exc
                if attempt + 1 >= attempts:
                    raise SectorsClientError(f"Sectors request failed: {exc}") from exc
            # Retries are disabled by default because they may consume more credits.
            time.sleep(min(4.0, (2**attempt) + random.random()))
        raise SectorsClientError(f"Sectors request failed: {last_error}")
