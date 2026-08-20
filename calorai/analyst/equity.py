"""Heat-equity analytics — who carries the heat burden, and how skewed it is.

Hsu et al. (Nature, 2021) showed urban heat disproportionately burdens
low-income neighbourhoods and communities of colour in 169 of 175 US
cities; Climate Central (2024) quantified per-capita UHI exposure.
This module turns the tile field into the standard equity metrics:

- Gini coefficient of the tile temperature distribution (0 = uniform,
  1 = extreme concentration).
- Quintile gap: mean temperature of the hottest 20% of tiles minus the
  coolest 20%.
- Exposure share: fraction of tiles above a stated threshold.
- Cross-district leaderboard: every district audited (mock or live) and
  ranked by composite burden, so a planner can see their city in context.
"""

from __future__ import annotations

from typing import Any

#: Default threshold for "dangerously hot surface tiles" (°C).
DEFAULT_THRESHOLD_C = 40.0


def gini(values: list[float]) -> float:
    """Gini coefficient of a list of values (0..1)."""
    n = len(values)
    if n < 2:
        return 0.0
    sorted_v = sorted(values)
    total = sum(sorted_v)
    if total <= 0.0:
        return 0.0
    # G = (2 * sum(i * x_i)) / (n * sum(x)) - (n + 1) / n
    return (2.0 * sum((i + 1) * v for i, v in enumerate(sorted_v))) / (
        n * total
    ) - (n + 1.0) / n


def quintile_gap_c(values: list[float]) -> float:
    """Mean of the hottest 20% minus mean of the coolest 20% (K)."""
    n = len(values)
    if n < 5:
        return max(values, default=0.0) - min(values, default=0.0)
    sorted_v = sorted(values)
    cut = max(1, n // 5)
    top = sum(sorted_v[-cut:]) / cut
    bottom = sum(sorted_v[:cut]) / cut
    return top - bottom


def heat_burden(
    tiles: list[dict[str, Any]], threshold_c: float = DEFAULT_THRESHOLD_C
) -> dict[str, Any]:
    """Equity profile of a tile field."""
    values = [t["value"] for t in tiles]
    if not values:
        return {"present": False}
    n = len(values)
    max_v = max(values)
    mean_v = sum(values) / n
    above = sum(1 for v in values if v >= threshold_c)
    return {
        "present": True,
        "n_tiles": n,
        "gini": round(gini(values), 4),
        "quintile_gap_c": round(quintile_gap_c(values), 2),
        "max_c": round(max_v, 2),
        "mean_c": round(mean_v, 2),
        "threshold_c": threshold_c,
        "share_above_threshold_pct": round(100.0 * above / n, 1),
        "hot_core_share_pct": round(
            100.0 * sum(1 for v in values if v >= max_v - 1.0) / n, 1
        ),
        "note": (
            "Gini/quintile-gap over the tile field; a high gap at small scale "
            "means the hottest blocks sit next to cool ones — targeting the "
            "top 20% of tiles captures most of the burden (Hsu et al. 2021)."
        ),
    }


def cross_district_leaderboard(
    keys: list[str], date: str, hour: int = 15, source: str = "mock"
) -> list[dict[str, Any]]:
    """Audit every district and rank by composite heat burden (ascending equity).

    Composite rank: mean WBGT, exceedance hours, vulnerability score,
    and heat-equity skew (Gini + quintile gap). Uses the standard
    AuditAgent pipeline — identical numbers to the per-district reports.
    """
    from calorai.agent import AuditAgent, AuditRequest  # lazy: avoids import cycle

    rows: list[dict[str, Any]] = []
    for key in keys:
        agent = AuditAgent(
            AuditRequest(district=key, date=date, hour=hour, data_source=source)
        )
        report = agent.run()
        analysis = report.get("analysis", {}) or {}
        equity = analysis.get("equity", {}) or {}
        exposure = report.get("exposure", {}) or {}
        vuln = report.get("vulnerability", {}) or {}
        score = vuln.get("score", {}) or {}
        rows.append(
            {
                "district": report.get("district", key),
                "key": key,
                "mean_c": report.get("snapshot", {}).get("mean_c"),
                "max_c": report.get("snapshot", {}).get("max_c"),
                "wbgt_c": exposure.get("wbgt_c"),
                "exceedance_hours": exposure.get("exceedance_hours"),
                "vulnerability": score.get("score"),
                "gini": equity.get("gini"),
                "quintile_gap_c": equity.get("quintile_gap_c"),
                "risk_band": exposure.get("level"),
            }
        )
    rows.sort(
        key=lambda r: (
            -(r["wbgt_c"] or 0.0),
            -(r["exceedance_hours"] or 0.0),
            -(r["vulnerability"] or 0.0),
        )
    )
    return rows