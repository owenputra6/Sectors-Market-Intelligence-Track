from __future__ import annotations

import asyncio
import re
import os
from contextlib import asynccontextmanager, suppress
from .weekly import WeeklyStore
from typing import Annotated

from fastapi import FastAPI, HTTPException, Path
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .config import settings
from .feature_engine import run_duel
from .market_intelligence import build_market_intelligence
from .sectors_client import SectorsClient, normalize_ticker


TICKER_PATTERN = re.compile(r"^[A-Z0-9]{2,12}$")


class DuelRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "ticker_a": "PANI",
                    "ticker_b": "BBCA",
                    "force_refresh": False,
                    "max_new_credits": 10,
                }
            ]
        }
    )

    ticker_a: str = Field(description="IDX ticker, with or without .JK")
    ticker_b: str = Field(description="IDX ticker, with or without .JK")
    force_refresh: bool = Field(
        default=False,
        description="Reserved for compatibility. Duel requests never refresh provider data.",
    )
    max_new_credits: int = Field(
        default=10,
        ge=0,
        le=100,
        description=(
            "Compatibility field. Interactive requests always read published CSV and cost 0."
        ),
    )

    @field_validator("ticker_a", "ticker_b")
    @classmethod
    def validate_ticker(cls, value: str) -> str:
        ticker = normalize_ticker(value)
        if not TICKER_PATTERN.fullmatch(ticker):
            raise ValueError("Ticker must contain 2-12 uppercase letters or digits.")
        return ticker

    @model_validator(mode="after")
    def different_tickers(self) -> "DuelRequest":
        if self.ticker_a == self.ticker_b:
            raise ValueError("A ticker cannot duel itself.")
        return self


client = SectorsClient(settings)
weekly = WeeklyStore(client)


@asynccontextmanager
async def lifespan(app):
    weekly.log_status()
    task = None
    if os.getenv('WEEKLY_REFRESH_ENABLED', 'true').strip().lower() in {'1', 'true', 'yes', 'on'}:
        task = asyncio.create_task(weekly.schedule())
    try:
        yield
    finally:
        if task:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task


app = FastAPI(
    lifespan=lifespan,
    title="Watcher Market Intelligence API",
    version="1.0.0",
    description=(
        "Weekly CSV market-intelligence backend. Sectors credentials stay on the server; "
        "browse, detail and duel routes only read the last complete published snapshot."
    ),
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)


def estimate_request(request: DuelRequest) -> dict[str, object]:
    weekly.load()
    partial = bool(weekly._manifest.get('partial'))
    tickers = [{'ticker': ticker,
                'state': ('cache_only_partial' if partial else 'published_csv')
                if ticker in weekly._stocks else 'missing',
                'estimated_new_credits': 0} for ticker in (request.ticker_a, request.ticker_b)]
    return {'tickers': tickers, 'force_refresh': request.force_refresh,
            'estimated_new_credits_upper_bound': 0, 'max_new_credits': request.max_new_credits,
            'within_budget': True, 'ready': all(t['state'] != 'missing' for t in tickers),
            'message': 'Duels read weekly CSV only. Refresh via scheduler or python -m app.refresh.'}


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "api_key_configured": bool(settings.api_key),
        "weekly_snapshot": weekly.status(),
        "report_sections": list(settings.report_sections),
        "provider_credits_per_company_refresh": client.section_cost,
        "local_cors_origin_regex": settings.cors_origin_regex,
    }


@app.get("/api/v1/cache/{ticker}")
def cache_status(
    ticker: Annotated[str, Path(description="IDX ticker, with or without .JK")]
) -> dict[str, object]:
    normalized = normalize_ticker(ticker)
    if not TICKER_PATTERN.fullmatch(normalized):
        raise HTTPException(status_code=422, detail="Invalid ticker format.")
    return client.cache_status(normalized)


@app.post("/api/v1/duels/estimate")
def duel_estimate(request: DuelRequest) -> dict[str, object]:
    """Local-only preflight; never contacts Sectors and never consumes credits."""
    return estimate_request(request)


@app.post("/api/v1/duels")
async def duel(request: DuelRequest) -> dict[str, object]:
    weekly.load()
    if request.force_refresh:
        raise HTTPException(409, 'Refresh is performed by the weekly scheduler or CLI, never by a duel.')
    stocks = [weekly._stocks.get(t) for t in (request.ticker_a, request.ticker_b)]
    if any(stock is None for stock in stocks):
        raise HTTPException(409, 'Ticker missing from weekly CSV. Add TRACKED_TICKERS and refresh with CLI when due.')
    response = run_duel(*stocks, max_missing_feature_rate=settings.max_missing_feature_rate)
    response['market_intelligence'] = build_market_intelligence(response)
    response['meta'] = {**weekly.status(), 'estimated_new_credits_upper_bound': 0,
                        'cache_policy': ('request-cache CSV; partial, no live requests'
                                         if weekly._manifest.get('partial')
                                         else 'published weekly CSV; no live requests'),
                        'sources': [{'ticker': t,
                                     'source': ('request_cache_csv' if weekly._manifest.get('partial') else 'weekly_csv'),
                                     'fetched_at': weekly._manifest.get('fetched_at'),
                                     'estimated_credits': 0} for t in (request.ticker_a, request.ticker_b)]}
    return response


@app.get('/api/v1/stocks')
def browse_stocks(q: str = ''):
    return weekly.browse(q)


@app.get('/api/v1/stocks/{ticker}')
def stock_profile(ticker: str):
    result = weekly.detail(ticker)
    if result['profile'] is None:
        raise HTTPException(404, 'Ticker not in the weekly snapshot. Configure TRACKED_TICKERS and refresh via CLI.')
    return result


@app.get('/api/v1/sectors')
def sector_benchmarks():
    weekly.load()
    return {'meta': weekly.status(), 'items': weekly._sectors}


@app.get('/api/v1/data-status')
def data_status():
    return weekly.status()
