from __future__ import annotations

import math
import statistics
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

from .sectors_client import normalize_ticker


SEGMENT_ORDER = ["Valuation", "Growth", "Financial", "Performance", "Dividend"]


def finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def safe_div(numerator: Any, denominator: Any) -> float | None:
    a, b = finite(numerator), finite(denominator)
    if a is None or b is None or b == 0:
        return None
    return a / b


def median(values: Iterable[Any], *, positive_only: bool = False) -> tuple[float | None, int]:
    clean = [value for item in values if (value := finite(item)) is not None]
    if positive_only:
        clean = [value for value in clean if value > 0]
    return (statistics.median(clean), len(clean)) if clean else (None, 0)


def _latest_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    valid: list[tuple[int, dict[str, Any]]] = []
    for row in rows or []:
        try:
            valid.append((int(row.get("year")), row))
        except (TypeError, ValueError):
            continue
    return [row for _, row in sorted(valid, key=lambda item: item[0])]


def _growth(current: Any, previous: Any) -> float | None:
    current_num, previous_num = finite(current), finite(previous)
    if current_num is None or previous_num is None or previous_num <= 0:
        return None
    return current_num / previous_num - 1


def _max_mapping_value(value: Any) -> float | None:
    if not isinstance(value, dict):
        return None
    valid = [number for item in value.values() if (number := finite(item)) is not None]
    return max(valid) if valid else None


def _ratio(row: dict[str, Any], numerator: str, denominator: str) -> float | None:
    return safe_div(row.get(numerator), row.get(denominator))


@dataclass
class StockSnapshot:
    ticker: str
    company_name: str | None = None
    sector: str | None = None
    sub_sector: str | None = None
    listing_board: str | None = None
    as_of: str | None = None
    last_close_price: float | None = None
    market_cap: float | None = None
    market_cap_rank: int | None = None
    pe_ttm: float | None = None
    pb_mrq: float | None = None
    intrinsic_value: float | None = None
    revenue_growth: float | None = None
    earnings_growth: float | None = None
    quarterly_earnings_growth: float | None = None
    roe: float | None = None
    roa: float | None = None
    net_margin: float | None = None
    market_cap_change_12m: float | None = None
    high_52w: float | None = None
    yield_ttm: float | None = None
    yield_5y: float | None = None
    yield_average_period: int | None = None
    payout_ratio: float | None = None
    cash_payout_ratio: float | None = None
    peer_medians: dict[str, float | None] = field(default_factory=dict)
    peer_counts: dict[str, int] = field(default_factory=dict)
    benchmark: dict[str, Any] = field(default_factory=dict)
    red_flags: list[dict[str, str]] = field(default_factory=list)

    def public_dict(self) -> dict[str, Any]:
        return asdict(self)


def _select_peer_block(
    report: dict[str, Any], ticker: str, sub_sector: str | None
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    candidates: list[tuple[int, list[dict[str, Any]], dict[str, Any]]] = []
    for block in report.get("peers") or []:
        data = block.get("peers_data") or {}
        rows = data.get("companies") or []
        group_name = data.get("group_name") or {}
        symbols = {normalize_ticker(row.get("symbol", "")) for row in rows}
        score = 0
        if ticker in symbols:
            score += 2
        if sub_sector and group_name.get("sub_sector") == sub_sector:
            score += 2
        if sub_sector and str(group_name.get("sub_sector", "")).casefold() == str(sub_sector).casefold():
            candidates.append((score, rows, group_name))
    if not candidates:
        return [], {}
    _, rows, group_name = max(candidates, key=lambda item: item[0])
    deduplicated: dict[str, dict[str, Any]] = {}
    for row in rows:
        symbol = normalize_ticker(row.get("symbol", ""))
        if symbol:
            deduplicated[symbol] = row
    return list(deduplicated.values()), group_name


def snapshot_from_report(
    ticker: str,
    report: dict[str, Any],
    *,
    min_valid_peers: int = 5,
) -> StockSnapshot:
    ticker = normalize_ticker(ticker)
    overview = report.get("overview") or {}
    valuation = report.get("valuation") or {}
    financials = report.get("financials") or {}
    dividend = report.get("dividend") or {}

    sub_sector = overview.get("sub_sector")
    peer_rows, peer_group = _select_peer_block(report, ticker, sub_sector)
    self_row = next(
        (
            row
            for row in peer_rows
            if normalize_ticker(row.get("symbol", "")) == ticker
            or "self" in (row.get("group") or [])
        ),
        {},
    )
    peer_only = [
        row
        for row in peer_rows
        if normalize_ticker(row.get("symbol", "")) != ticker
        and "self" not in (row.get("group") or [])
    ]

    annual = _latest_rows(financials.get("historical_financials") or [])
    latest_annual = annual[-1] if annual else {}
    previous_annual = annual[-2] if len(annual) >= 2 else {}

    pe_median, pe_n = median((row.get("pe_ttm") for row in peer_only), positive_only=True)
    pb_median, pb_n = median((row.get("pb_mrq") for row in peer_only), positive_only=True)
    roe_median, roe_n = median(
        (_ratio(row, "net_income", "total_equity") for row in peer_only)
    )
    roa_median, roa_n = median(
        (_ratio(row, "net_income", "total_assets") for row in peer_only)
    )
    margin_median, margin_n = median(
        (_ratio(row, "net_income", "total_revenue") for row in peer_only)
    )
    return_median, return_n = median(
        (row.get("yearly_mcap_chg") for row in peer_only)
    )

    all_time_price = overview.get("all_time_price") or {}
    yield_avg = dividend.get("dividend_yield_avg") or {}
    last_price = finite(overview.get("last_close_price"))
    if last_price is None:
        last_price = finite(valuation.get("last_close_price"))

    snapshot = StockSnapshot(
        ticker=ticker,
        company_name=report.get("company_name"),
        sector=overview.get("sector") or peer_group.get("sector"),
        sub_sector=sub_sector or peer_group.get("sub_sector"),
        listing_board=overview.get("listing_board"),
        as_of=overview.get("latest_close_date") or valuation.get("latest_close_date"),
        last_close_price=last_price,
        market_cap=finite(overview.get("market_cap")),
        market_cap_rank=overview.get("market_cap_rank"),
        # One consistent source: self row from the same peer table used for medians.
        pe_ttm=finite(self_row.get("pe_ttm")),
        pb_mrq=finite(self_row.get("pb_mrq")),
        intrinsic_value=finite(valuation.get("intrinsic_value")),
        revenue_growth=_growth(
            latest_annual.get("revenue"), previous_annual.get("revenue")
        ),
        earnings_growth=_growth(
            latest_annual.get("earnings"), previous_annual.get("earnings")
        ),
        quarterly_earnings_growth=finite(
            financials.get("yoy_quarter_earnings_growth")
        ),
        # Same formula for company and peers, avoiding mixed ratio definitions.
        roe=_ratio(self_row, "net_income", "total_equity"),
        roa=_ratio(self_row, "net_income", "total_assets"),
        net_margin=_ratio(self_row, "net_income", "total_revenue"),
        market_cap_change_12m=finite(self_row.get("yearly_mcap_chg")),
        high_52w=_max_mapping_value(all_time_price.get("52_w_high")),
        yield_ttm=finite(dividend.get("yield_ttm")),
        yield_5y=finite(yield_avg.get("avg_yield")),
        yield_average_period=yield_avg.get("period"),
        payout_ratio=finite(dividend.get("payout_ratio")),
        cash_payout_ratio=finite(dividend.get("cash_payout_ratio")),
        peer_medians={
            "pe_ttm": pe_median,
            "pb_mrq": pb_median,
            "roe": roe_median,
            "roa": roa_median,
            "net_margin": margin_median,
            "market_cap_change_12m": return_median,
        },
        peer_counts={
            "pe_ttm": pe_n,
            "pb_mrq": pb_n,
            "roe": roe_n,
            "roa": roa_n,
            "net_margin": margin_n,
            "market_cap_change_12m": return_n,
        },
    )

    board = (snapshot.listing_board or "").lower()
    if any(word in board for word in ("watch", "monitor", "pemantauan")):
        snapshot.red_flags.append(
            {
                "code": "WATCHLIST_BOARD",
                "message": f"Listing board requires attention: {snapshot.listing_board}.",
            }
        )
    if snapshot.intrinsic_value is not None and snapshot.intrinsic_value <= 0:
        snapshot.red_flags.append(
            {
                "code": "NONPOSITIVE_INTRINSIC",
                "message": "Sectors intrinsic value is zero or negative.",
            }
        )
    if snapshot.cash_payout_ratio is not None and snapshot.cash_payout_ratio < 0:
        snapshot.red_flags.append(
            {
                "code": "NEGATIVE_CASH_PAYOUT",
                "message": "Cash payout ratio is negative.",
            }
        )
    if snapshot.cash_payout_ratio is not None and snapshot.cash_payout_ratio > 1:
        snapshot.red_flags.append(
            {
                "code": "CASH_PAYOUT_ABOVE_100",
                "message": "Cash payout ratio is above 100%.",
            }
        )
    operating_cash_flow = finite(latest_annual.get("operating_cash_flow"))
    if operating_cash_flow is not None and operating_cash_flow < 0:
        snapshot.red_flags.append(
            {
                "code": "NEGATIVE_OPERATING_CASH_FLOW",
                "message": "Latest annual operating cash flow is negative.",
            }
        )
    thin_metrics = [
        key for key, count in snapshot.peer_counts.items() if count < min_valid_peers
    ]
    if thin_metrics:
        snapshot.red_flags.append(
            {
                "code": "LOW_PEER_COVERAGE",
                "message": "Peer median has fewer than "
                f"{min_valid_peers} valid observations for: {', '.join(thin_metrics)}.",
            }
        )
    return snapshot


@dataclass(frozen=True)
class MetricDefinition:
    number: int
    segment: str
    key: str
    label: str
    direction: str


METRICS = [
    MetricDefinition(1, "Valuation", "pe", "P/E", "lower"),
    MetricDefinition(2, "Valuation", "pb", "P/B", "lower"),
    MetricDefinition(3, "Valuation", "price_intrinsic", "Price / Sectors intrinsic", "lower"),
    MetricDefinition(4, "Growth", "revenue_growth", "Revenue growth FY", "higher"),
    MetricDefinition(5, "Growth", "earnings_growth", "Earnings growth FY", "higher"),
    MetricDefinition(6, "Growth", "quarter_growth", "Quarter earnings YoY", "higher"),
    MetricDefinition(7, "Financial", "roe", "ROE", "higher"),
    MetricDefinition(8, "Financial", "roa", "ROA", "higher"),
    MetricDefinition(9, "Financial", "net_margin", "Net margin", "higher"),
    MetricDefinition(10, "Performance", "total_return", "Total return 12M proxy", "higher"),
    MetricDefinition(11, "Performance", "relative_return", "12M return vs peers", "higher"),
    MetricDefinition(12, "Performance", "near_52w_high", "Price / 52W high", "higher"),
    MetricDefinition(13, "Dividend", "yield_ttm", "Dividend yield TTM", "higher"),
    MetricDefinition(14, "Dividend", "yield_5y", "Average dividend yield", "higher"),
    MetricDefinition(15, "Dividend", "payout", "Payout ratio", "higher"),
]


@dataclass(frozen=True)
class Comparable:
    value: float | None
    raw_value: float | None
    baseline: float | None
    basis: str
    validity: str = "valid"


def _comparable(snapshot: StockSnapshot, key: str, same_subsector: bool) -> Comparable:
    if key == "pe":
        raw, baseline = snapshot.pe_ttm, snapshot.peer_medians.get("pe_ttm")
        if raw is not None and raw <= 0:
            return Comparable(None, raw, baseline, "raw" if same_subsector else "raw / peer median", "nonpositive")
        value = raw if same_subsector else safe_div(raw, baseline)
        return Comparable(value, raw, baseline, "raw" if same_subsector else "raw / peer median")
    if key == "pb":
        raw, baseline = snapshot.pb_mrq, snapshot.peer_medians.get("pb_mrq")
        if raw is not None and raw <= 0:
            return Comparable(None, raw, baseline, "raw" if same_subsector else "raw / peer median", "nonpositive")
        value = raw if same_subsector else safe_div(raw, baseline)
        return Comparable(value, raw, baseline, "raw" if same_subsector else "raw / peer median")
    if key == "price_intrinsic":
        raw, intrinsic = snapshot.last_close_price, snapshot.intrinsic_value
        if intrinsic is not None and intrinsic <= 0:
            return Comparable(None, raw, intrinsic, "price / Sectors intrinsic", "nonpositive_intrinsic")
        return Comparable(safe_div(raw, intrinsic), raw, intrinsic, "price / Sectors intrinsic")
    if key == "revenue_growth":
        return Comparable(snapshot.revenue_growth, snapshot.revenue_growth, None, "raw")
    if key == "earnings_growth":
        return Comparable(snapshot.earnings_growth, snapshot.earnings_growth, None, "raw")
    if key == "quarter_growth":
        return Comparable(snapshot.quarterly_earnings_growth, snapshot.quarterly_earnings_growth, None, "raw")
    if key in {"roe", "roa", "net_margin"}:
        raw = getattr(snapshot, key)
        baseline = snapshot.peer_medians.get(key)
        value = raw if same_subsector else (
            raw - baseline if raw is not None and baseline is not None else None
        )
        return Comparable(value, raw, baseline, "raw" if same_subsector else "raw - peer median")
    if key == "total_return":
        if snapshot.market_cap_change_12m is None or snapshot.yield_ttm is None:
            value = None
        else:
            value = snapshot.market_cap_change_12m + snapshot.yield_ttm
        return Comparable(value, value, None, "market-cap change 12M + yield TTM")
    if key == "relative_return":
        raw = snapshot.market_cap_change_12m
        baseline = snapshot.peer_medians.get("market_cap_change_12m")
        value = raw if same_subsector else (
            raw - baseline if raw is not None and baseline is not None else None
        )
        return Comparable(value, raw, baseline, "raw" if same_subsector else "raw - peer median")
    if key == "near_52w_high":
        return Comparable(
            safe_div(snapshot.last_close_price, snapshot.high_52w),
            snapshot.last_close_price,
            snapshot.high_52w,
            "last close / 52W high",
        )
    if key == "yield_ttm":
        return Comparable(snapshot.yield_ttm, snapshot.yield_ttm, None, "raw")
    if key == "yield_5y":
        return Comparable(snapshot.yield_5y, snapshot.yield_5y, None, "raw")
    if key == "payout":
        return Comparable(snapshot.payout_ratio, snapshot.payout_ratio, None, "raw")
    raise KeyError(key)


def _compare(
    ticker_a: str,
    ticker_b: str,
    a: Comparable,
    b: Comparable,
    direction: str,
) -> tuple[str, str]:
    # Explicit nonpositive values lose to a valid positive value. This prevents
    # negative earnings or intrinsic value from appearing artificially cheap.
    invalid_states = {"nonpositive", "nonpositive_intrinsic"}
    a_invalid, b_invalid = a.validity in invalid_states, b.validity in invalid_states
    if a_invalid != b_invalid:
        return (ticker_b, "invalid_value") if a_invalid else (ticker_a, "invalid_value")
    if a_invalid and b_invalid:
        return "draw", "both_invalid"
    if a.value is None or b.value is None:
        return "draw", "missing_data"
    if math.isclose(a.value, b.value, rel_tol=1e-6, abs_tol=1e-12):
        return "draw", "equal_value"
    a_wins = a.value < b.value if direction == "lower" else a.value > b.value
    return (ticker_a if a_wins else ticker_b), "compared"


# Continuous feature-point share. The official duel/segment verdict remains
# win-count based. This only removes the quantized n/15 and n/3 presentation.
FEATURE_TILT_WEIGHT = 0.45


def _relative_margin(a: float | None, b: float | None) -> float:
    """Return a scale-free distance between two comparable values in [0, 1]."""
    if a is None or b is None:
        return 0.0
    scale = abs(a) + abs(b)
    if scale == 0:
        return 0.0
    return min(1.0, abs(a - b) / scale)


def _feature_margin(row: dict[str, Any]) -> float:
    """Return how decisively a valid feature was won, in [0, 1]."""
    if row["winner"] == "draw":
        return 0.0
    if row["reason"] == "invalid_value":
        return 1.0
    return _relative_margin(row["value_a"], row["value_b"])


def _continuous_points(
    rows: list[dict[str, Any]], ticker_a: str
) -> float | None:
    """Return stock A's continuous point total across already-valid rows."""
    if not rows:
        return None
    wins_a = sum(row["winner"] == ticker_a for row in rows)
    draws = sum(row["winner"] == "draw" for row in rows)
    decided = len(rows) - draws
    margin_a = sum(
        _feature_margin(row) for row in rows if row["winner"] == ticker_a
    )
    margin_b = sum(
        _feature_margin(row)
        for row in rows
        if row["winner"] not in (ticker_a, "draw")
    )
    tilt = 0.0 if decided == 0 else (margin_a - margin_b) / decided
    points = wins_a + draws * 0.5 + FEATURE_TILT_WEIGHT * tilt
    return min(max(points, 0.0), float(len(rows)))


def _feature_is_valid(row: dict[str, Any]) -> bool:
    """Return whether both stocks have a scoreable comparable value."""
    return (
        row.get("value_a") is not None
        and row.get("value_b") is not None
        and row.get("reason")
        not in {"missing_data", "invalid_value", "both_invalid"}
    )


def run_duel(
    stock_a: StockSnapshot,
    stock_b: StockSnapshot,
    *,
    max_missing_feature_rate: float = 0.35,
) -> dict[str, Any]:
    same_subsector = bool(
        stock_a.sub_sector
        and stock_b.sub_sector
        and stock_a.sub_sector == stock_b.sub_sector
    )
    features: list[dict[str, Any]] = []
    for metric in METRICS:
        a = _comparable(stock_a, metric.key, same_subsector)
        b = _comparable(stock_b, metric.key, same_subsector)
        winner, reason = _compare(
            stock_a.ticker, stock_b.ticker, a, b, metric.direction
        )
        features.append(
            {
                "number": metric.number,
                "segment": metric.segment,
                "key": metric.key,
                "label": metric.label,
                "direction": metric.direction,
                "comparison_basis": a.basis,
                "ticker_a": stock_a.ticker,
                "value_a": a.value,
                "raw_value_a": a.raw_value,
                "baseline_a": a.baseline,
                "validity_a": a.validity,
                "ticker_b": stock_b.ticker,
                "value_b": b.value,
                "raw_value_b": b.raw_value,
                "baseline_b": b.baseline,
                "validity_b": b.validity,
                "winner": winner,
                "reason": reason,
            }
        )

    segments: list[dict[str, Any]] = []
    for segment in SEGMENT_ORDER:
        rows = [row for row in features if row["segment"] == segment]
        valid_rows = [row for row in rows if _feature_is_valid(row)]
        wins_a = sum(row["winner"] == stock_a.ticker for row in valid_rows)
        wins_b = sum(row["winner"] == stock_b.ticker for row in valid_rows)
        draws = sum(row["winner"] == "draw" for row in valid_rows)
        valid_count = len(valid_rows)
        points_a = _continuous_points(valid_rows, stock_a.ticker)
        share_a = (
            round(100 * points_a / valid_count, 2)
            if points_a is not None else None
        )
        share_b = round(100 - share_a, 2) if share_a is not None else None
        if valid_count < 2 or wins_a == wins_b:
            winner = "draw"
        else:
            winner = stock_a.ticker if wins_a > wins_b else stock_b.ticker
        segments.append(
            {
                "segment": segment,
                "wins_a": wins_a,
                "wins_b": wins_b,
                "draws": draws,
                "valid_features": valid_count,
                "missing_features": len(rows) - valid_count,
                "point_share_a": share_a,
                "point_share_b": share_b,
                "winner": winner,
            }
        )

    segment_wins_a = sum(row["winner"] == stock_a.ticker for row in segments)
    segment_wins_b = sum(row["winner"] == stock_b.ticker for row in segments)
    segment_draws = sum(row["winner"] == "draw" for row in segments)
    valid_features = [row for row in features if _feature_is_valid(row)]
    missing_count = len(features) - len(valid_features)
    feature_wins_a = sum(row["winner"] == stock_a.ticker for row in valid_features)
    feature_wins_b = sum(row["winner"] == stock_b.ticker for row in valid_features)
    feature_draws = sum(row["winner"] == "draw" for row in valid_features)
    feature_points_a = _continuous_points(valid_features, stock_a.ticker)
    feature_share_a = (
        round(100 * feature_points_a / len(valid_features), 2)
        if feature_points_a is not None else None
    )
    feature_share_b = round(100 - feature_share_a, 2) if feature_share_a is not None else None
    missing_rate = missing_count / len(features)
    verdict_available = missing_rate <= max_missing_feature_rate
    if not verdict_available:
        final_winner = "unavailable"
        score_a = None
        score_b = None
    elif segment_wins_a == segment_wins_b:
        final_winner = "draw"
        score_a = score_b = 0
    elif segment_wins_a > segment_wins_b:
        final_winner = stock_a.ticker
        score_a, score_b = 1, -1
    else:
        final_winner = stock_b.ticker
        score_a, score_b = -1, 1

    segment_names_a = [row["segment"] for row in segments if row["winner"] == stock_a.ticker]
    segment_names_b = [row["segment"] for row in segments if row["winner"] == stock_b.ticker]
    if final_winner == "unavailable":
        narrative = (
            f"Verdict {stock_a.ticker} vs {stock_b.ticker} tidak ditampilkan karena "
            f"{missing_rate:.1%} fitur tidak memiliki pasangan data lengkap."
        )
    elif final_winner == "draw":
        narrative = (
            f"{stock_a.ticker} dan {stock_b.ticker} seri di level segmen "
            f"({segment_wins_a}:{segment_wins_b}, {segment_draws} segmen seri)."
        )
    else:
        loser = stock_b.ticker if final_winner == stock_a.ticker else stock_a.ticker
        winner_segments = segment_names_a if final_winner == stock_a.ticker else segment_names_b
        narrative = (
            f"{final_winner} menang atas {loser} dengan skor segmen "
            f"{max(segment_wins_a, segment_wins_b)}:{min(segment_wins_a, segment_wins_b)}. "
            f"Kemenangan datang dari {', '.join(winner_segments)}."
        )

    return {
        "comparison": {
            "ticker_a": stock_a.ticker,
            "ticker_b": stock_b.ticker,
            "same_subsector": same_subsector,
            "normalization_rule": (
                "raw_same_subsector" if same_subsector else "peer_adjusted_cross_subsector"
            ),
            "peer_scope": "Exact subsector peers; target excluded. P/E uses official subsector statistics when supplied by backend.",
        },
        "stocks": {
            stock_a.ticker: stock_a.public_dict(),
            stock_b.ticker: stock_b.public_dict(),
        },
        "features": features,
        "segments": segments,
        "verdict": {
            "available": verdict_available,
            "winner": final_winner,
            "segment_wins_a": segment_wins_a,
            "segment_wins_b": segment_wins_b,
            "segment_draws": segment_draws,
            "score_a": score_a,
            "score_b": score_b,
            # Continuous presentation score: one point per win, half per draw,
            # plus a capped margin tilt. Missing pairs are excluded. The
            # official duel winner above remains segment-majority based.
            "feature_wins_a": feature_wins_a,
            "feature_wins_b": feature_wins_b,
            "feature_draws": feature_draws,
            "valid_features": len(valid_features),
            "feature_point_share_a": feature_share_a,
            "feature_point_share_b": feature_share_b,
            "missing_features": missing_count,
            "missing_feature_rate": missing_rate,
        },
        "narrative": narrative,
    }
