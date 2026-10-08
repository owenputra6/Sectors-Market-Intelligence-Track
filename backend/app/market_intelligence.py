from __future__ import annotations

from typing import Any


SEGMENT_CONTEXT = {
    "Valuation": {
        "title": "Valuation context",
        "win": "shows the more attractive valuation profile after applying the duel's sector-aware comparison rules",
        "draw": "does not produce a clear valuation advantage",
    },
    "Growth": {
        "title": "Growth pulse",
        "win": "shows the stronger recent top-line and earnings growth profile",
        "draw": "does not produce a clear recent growth advantage",
    },
    "Financial": {
        "title": "Operating quality",
        "win": "shows the stronger profitability profile relative to its own operating context",
        "draw": "does not produce a clear profitability advantage",
    },
    "Performance": {
        "title": "Market performance",
        "win": "shows the stronger 12-month market-performance and price-position profile",
        "draw": "does not produce a clear market-performance advantage",
    },
    "Dividend": {
        "title": "Shareholder distribution",
        "win": "shows the stronger dividend distribution profile under the supplied scoring rules",
        "draw": "does not produce a clear dividend advantage",
    },
}


def _feature_counts(features: list[dict[str, Any]], ticker_a: str, ticker_b: str) -> dict[str, int]:
    valid = [row for row in features if row.get("reason") != "missing_data"]
    return {
        ticker_a: sum(row.get("winner") == ticker_a for row in valid),
        ticker_b: sum(row.get("winner") == ticker_b for row in valid),
        "draw": sum(row.get("winner") == "draw" for row in valid),
        "missing": len(features) - len(valid),
    }


def _confidence(verdict: dict[str, Any], feature_count: int) -> dict[str, Any]:
    missing = int(verdict.get("missing_features") or 0)
    coverage = 1.0 - (missing / feature_count if feature_count else 1.0)
    margin = abs(
        int(verdict.get("segment_wins_a") or 0)
        - int(verdict.get("segment_wins_b") or 0)
    )
    if not verdict.get("available") or coverage < 0.65:
        level = "low"
    elif coverage >= 0.90 and margin >= 2:
        level = "high"
    else:
        level = "moderate"
    return {
        "level": level,
        "coverage": coverage,
        "segment_margin": margin,
        "explanation": (
            f"{coverage:.0%} feature coverage with a {margin}-segment lead. "
            "Confidence describes result completeness and separation, not forecast certainty."
        ),
    }


def _segment_driver(
    segment: dict[str, Any],
    features: list[dict[str, Any]],
) -> dict[str, Any]:
    name = str(segment["segment"])
    winner = str(segment["winner"])
    context = SEGMENT_CONTEXT[name]
    rows = [row for row in features if row.get("segment") == name]
    decisive = [row for row in rows if row.get("winner") != "draw"]
    evidence = [
        {
            "feature_number": row.get("number"),
            "feature": row.get("label"),
            "winner": row.get("winner"),
            "value_a": row.get("value_a"),
            "value_b": row.get("value_b"),
            "raw_value_a": row.get("raw_value_a"),
            "raw_value_b": row.get("raw_value_b"),
            "baseline_a": row.get("baseline_a"),
            "baseline_b": row.get("baseline_b"),
            "basis": row.get("comparison_basis"),
            "reason": row.get("reason"),
        }
        for row in decisive
    ]
    if winner == "draw":
        insight = f"This segment {context['draw']}."
    else:
        won_labels = [row["label"] for row in rows if row.get("winner") == winner]
        share_a = segment.get("point_share_a")
        share_b = segment.get("point_share_b")
        share_text = (
            f" Continuous share: {share_a:.1f}% versus {share_b:.1f}%."
            if isinstance(share_a, (int, float)) and isinstance(share_b, (int, float))
            else ""
        )
        insight = (
            f"{winner} {context['win']}. "
            f"It leads on {', '.join(won_labels) if won_labels else 'the segment aggregate'}."
            f"{share_text}"
        )
    return {
        "segment": name,
        "title": context["title"],
        "leader": winner,
        "score": {
            "wins_a": segment.get("wins_a", 0),
            "wins_b": segment.get("wins_b", 0),
            "draws": segment.get("draws", 0),
            "point_share_a": segment.get("point_share_a"),
            "point_share_b": segment.get("point_share_b"),
            "missing_features": segment.get("missing_features", 0),
        },
        "insight": insight,
        "evidence": evidence,
    }


def _risk_watch(stocks: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    risks: list[dict[str, str]] = []
    for ticker, stock in stocks.items():
        last_close = stock.get("last_close_price")
        high_52w = stock.get("high_52w")
        if isinstance(last_close, (int, float)) and isinstance(high_52w, (int, float)) and high_52w > 0:
            drawdown = max(0.0, 1 - last_close / high_52w)
            if drawdown > 0:
                risks.append(
                    {
                        "ticker": ticker,
                        "code": "DRAWDOWN_52W",
                        "severity": "high" if drawdown >= 0.40 else "medium",
                        "message": (
                            f"Price is {drawdown:.1%} below its 52-week high; "
                            "a positive 12-month return can still coexist with this drawdown."
                        ),
                    }
                )
        for flag in stock.get("red_flags") or []:
            code = str(flag.get("code") or "DATA_WARNING")
            severity = "high" if code in {
                "WATCHLIST_BOARD",
                "NEGATIVE_OPERATING_CASH_FLOW",
                "NONPOSITIVE_INTRINSIC",
            } else "medium"
            risks.append(
                {
                    "ticker": ticker,
                    "code": code,
                    "severity": severity,
                    "message": str(flag.get("message") or "Review this data point."),
                }
            )
    return risks


def build_market_intelligence(duel: dict[str, Any]) -> dict[str, Any]:
    """Build concise, auditable reasoning from the duel output.

    This is deliberately deterministic: every statement maps to feature,
    segment, risk, or coverage data already present in the response.
    """

    comparison = duel["comparison"]
    verdict = duel["verdict"]
    features = duel["features"]
    segments = duel["segments"]
    stocks = duel["stocks"]
    ticker_a = comparison["ticker_a"]
    ticker_b = comparison["ticker_b"]
    counts = _feature_counts(features, ticker_a, ticker_b)
    confidence = _confidence(verdict, len(features))
    drivers = [_segment_driver(segment, features) for segment in segments]

    if not verdict.get("available"):
        headline = "Evidence coverage is insufficient for a reliable duel verdict"
        executive_summary = (
            f"The {ticker_a} versus {ticker_b} comparison is withheld because too many "
            "features lack a complete pair of values. Review the missing observations before "
            "using this report for screening."
        )
        tradeoff = "No relative thesis is issued while the coverage guard is active."
    elif verdict.get("winner") == "draw":
        headline = f"{ticker_a} and {ticker_b} present a balanced five-segment profile"
        executive_summary = (
            f"Neither stock establishes a segment-level majority. At feature level, {ticker_a} "
            f"leads {counts[ticker_a]} metrics, {ticker_b} leads {counts[ticker_b]}, and "
            f"{counts['draw']} are draws. The choice therefore depends on which segment matters "
            "most to the investor's mandate."
        )
        tradeoff = "The framework identifies different strengths, but no broad winner."
    else:
        winner = verdict["winner"]
        loser = ticker_b if winner == ticker_a else ticker_a
        winner_segment_count = max(
            int(verdict.get("segment_wins_a") or 0),
            int(verdict.get("segment_wins_b") or 0),
        )
        loser_segment_count = min(
            int(verdict.get("segment_wins_a") or 0),
            int(verdict.get("segment_wins_b") or 0),
        )
        winner_segments = [row["segment"] for row in segments if row["winner"] == winner]
        loser_segments = [row["segment"] for row in segments if row["winner"] == loser]
        winner_share = (
            verdict.get("feature_point_share_a")
            if winner == ticker_a
            else verdict.get("feature_point_share_b")
        )
        loser_share = (
            verdict.get("feature_point_share_b")
            if winner == ticker_a
            else verdict.get("feature_point_share_a")
        )
        continuous_score = (
            f" Feature-point share is {winner_share:.1f}% versus {loser_share:.1f}%."
            if winner_share is not None and loser_share is not None
            else ""
        )
        headline = f"{winner} holds the broader relative profile across the five-segment framework"
        executive_summary = (
            f"{winner} leads {winner_segment_count} of five segments and wins "
            f"{counts[winner]} individual features.{continuous_score} Its advantage is concentrated in "
            f"{', '.join(winner_segments)}. This is a relative screening result, not a price target "
            "or automatic buy signal."
        )
        tradeoff = (
            f"{loser} still leads in {', '.join(loser_segments)}; that counter-strength should be "
            "weighed against the mandate before acting."
            if loser_segments
            else f"{loser} does not lead a full segment, but individual feature wins may still matter."
        )

    return {
        "headline": headline,
        "executive_summary": executive_summary,
        "confidence": confidence,
        "feature_score": counts,
        "segment_drivers": drivers,
        "tradeoff": tradeoff,
        "risk_watch": _risk_watch(stocks),
        "comparison_logic": (
            "Same-subsector duels use raw comparable values. Cross-subsector duels compare each "
            "stock with its own Sectors peer median before the two relative positions are ranked."
        ),
        "decision_frame": (
            "Use this report to compare valuation, growth, profitability, market performance, and "
            "dividend profiles. Add liquidity, governance, balance-sheet, event, and portfolio-fit "
            "checks before making an investment decision."
        ),
        "disclaimer": "Deterministic market-intelligence summary; not investment advice.",
    }
