from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from metrics import avg_engagement_time, conversion_rate, ctr, z_test_proportions
from models import ABTestAssignment, ABTestEvent, EventType, Variant


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _event_counts(db: Session, test_id: int) -> dict[str, dict[str, int]]:
    """Impression / click / purchase counts grouped by variant."""
    rows = (
        db.query(ABTestEvent.variant, ABTestEvent.event_type, func.count().label("n"))
        .filter(
            ABTestEvent.test_id == test_id,
            ABTestEvent.event_type.in_(
                [EventType.IMPRESSION, EventType.CLICK, EventType.PURCHASE]
            ),
        )
        .group_by(ABTestEvent.variant, ABTestEvent.event_type)
        .all()
    )
    counts: dict[str, dict[str, int]] = {
        v.value: {"impression": 0, "click": 0, "purchase": 0} for v in Variant
    }
    for variant, event_type, n in rows:
        if variant is not None:
            counts[variant.value][event_type.value] = n
    return counts


def _users_exposed(db: Session, test_id: int) -> dict[str, int]:
    """Distinct users assigned to each variant."""
    rows = (
        db.query(
            ABTestAssignment.variant,
            func.count(ABTestAssignment.user_id).label("n"),
        )
        .filter(ABTestAssignment.test_id == test_id)
        .group_by(ABTestAssignment.variant)
        .all()
    )
    exposed = {v.value: 0 for v in Variant}
    for variant, n in rows:
        exposed[variant.value] = n
    return exposed


def _users_converted(db: Session, test_id: int) -> dict[str, int]:
    """Distinct users who made a purchase per variant."""
    rows = (
        db.query(
            ABTestEvent.variant,
            func.count(ABTestEvent.user_id.distinct()).label("n"),
        )
        .filter(
            ABTestEvent.test_id == test_id,
            ABTestEvent.event_type == EventType.PURCHASE,
        )
        .group_by(ABTestEvent.variant)
        .all()
    )
    converted = {v.value: 0 for v in Variant}
    for variant, n in rows:
        if variant is not None:
            converted[variant.value] = n
    return converted


def _engagement_times(db: Session, test_id: int) -> dict[str, list[float]]:
    """
    Engagement time values per variant.

    engagement_time events have null test_id, so we attribute them to a test
    by joining through ab_test_assignments on user_id.
    """
    rows = (
        db.query(ABTestAssignment.variant, ABTestEvent.value)
        .join(
            ABTestEvent,
            and_(
                ABTestEvent.user_id == ABTestAssignment.user_id,
                ABTestEvent.event_type == EventType.ENGAGEMENT_TIME,
            ),
        )
        .filter(ABTestAssignment.test_id == test_id)
        .all()
    )
    times: dict[str, list[float]] = {v.value: [] for v in Variant}
    for variant, value in rows:
        if value is not None:
            times[variant.value].append(value)
    return times


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def calculate_metrics_by_variant(db: Session, test_id: int) -> dict:
    """
    Return CTR, conversion rate, and average engagement time for each variant,
    plus an absolute and relative lift comparing B against A.
    """
    counts = _event_counts(db, test_id)
    exposed = _users_exposed(db, test_id)
    converted = _users_converted(db, test_id)
    eng = _engagement_times(db, test_id)

    variants: dict[str, dict] = {}
    for v in ("A", "B"):
        imp = counts[v]["impression"]
        clk = counts[v]["click"]
        exp = exposed[v]
        conv = converted[v]
        variants[v] = {
            "impressions": imp,
            "clicks": clk,
            "users_exposed": exp,
            "users_converted": conv,
            "avg_engagement_time_s": round(avg_engagement_time(eng[v]), 2),
            "ctr": round(ctr(imp, clk), 4),
            "conversion_rate": round(conversion_rate(exp, conv), 4),
        }

    a, b = variants["A"], variants["B"]
    lift = {
        "ctr_absolute": round(b["ctr"] - a["ctr"], 4),
        "ctr_relative_pct": round(
            (b["ctr"] - a["ctr"]) / a["ctr"] * 100 if a["ctr"] > 0 else 0.0, 2
        ),
        "conversion_rate_absolute": round(
            b["conversion_rate"] - a["conversion_rate"], 4
        ),
        "conversion_rate_relative_pct": round(
            (b["conversion_rate"] - a["conversion_rate"]) / a["conversion_rate"] * 100
            if a["conversion_rate"] > 0
            else 0.0,
            2,
        ),
    }

    return {"test_id": test_id, "variants": variants, "lift": lift}


def get_statistical_analysis(db: Session, test_id: int) -> dict:
    """
    Full A/B analysis: per-variant metrics + two-proportion z-tests for
    CTR and conversion rate.
    """
    metrics = calculate_metrics_by_variant(db, test_id)
    a = metrics["variants"]["A"]
    b = metrics["variants"]["B"]

    return {
        "test_id": test_id,
        "variants": metrics["variants"],
        "lift": metrics["lift"],
        "statistical_tests": {
            "ctr": z_test_proportions(
                n_a=a["impressions"],
                p_a=a["ctr"],
                n_b=b["impressions"],
                p_b=b["ctr"],
            ),
            "conversion_rate": z_test_proportions(
                n_a=a["users_exposed"],
                p_a=a["conversion_rate"],
                n_b=b["users_exposed"],
                p_b=b["conversion_rate"],
            ),
        },
    }


def aggregate_by_time(
    db: Session,
    test_id: int,
    period: str = "day",
) -> list[dict]:
    """
    Impressions, clicks, and CTR per variant, bucketed by time period.

    period: 'day' (default) or 'hour'.
    Note: strftime is SQLite-specific; swap for date_trunc on PostgreSQL.
    """
    if period not in ("day", "hour"):
        raise ValueError(f"period must be 'day' or 'hour', got {period!r}")

    fmt = "%Y-%m-%d" if period == "day" else "%Y-%m-%dT%H"

    rows = (
        db.query(
            func.strftime(fmt, ABTestEvent.timestamp).label("bucket"),
            ABTestEvent.variant,
            ABTestEvent.event_type,
            func.count().label("n"),
        )
        .filter(
            ABTestEvent.test_id == test_id,
            ABTestEvent.event_type.in_([EventType.IMPRESSION, EventType.CLICK]),
        )
        .group_by("bucket", ABTestEvent.variant, ABTestEvent.event_type)
        .order_by("bucket", ABTestEvent.variant)
        .all()
    )

    # Accumulate into {bucket: {variant: {impressions, clicks}}}
    buckets: dict[str, dict] = {}
    for bucket, variant, event_type, n in rows:
        if bucket not in buckets:
            buckets[bucket] = {
                "period": bucket,
                "A": {"impressions": 0, "clicks": 0},
                "B": {"impressions": 0, "clicks": 0},
            }
        if variant is not None:
            key = "impressions" if event_type == EventType.IMPRESSION else "clicks"
            buckets[bucket][variant.value][key] = n

    result = []
    for entry in sorted(buckets.values(), key=lambda x: x["period"]):
        row: dict = {"period": entry["period"]}
        for v in ("A", "B"):
            imp = entry[v]["impressions"]
            clk = entry[v]["clicks"]
            row[v] = {"impressions": imp, "clicks": clk, "ctr": round(ctr(imp, clk), 4)}
        result.append(row)

    return result
