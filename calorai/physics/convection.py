"""Convective exchange — wind-aware Newton's law coefficients.

The convective coefficient h_c is not a constant: under forced
convection the classic McAdams correlation for a flat, smooth surface is

    h_c = 5.7 + 3.8 · u        (W/m²·K, u in m/s)

covering the still-air limit ≈ 5.7 through a light breeze ≈ 12
(u ≈ 1.7 m/s) up to ~25 W/m²·K in a stiff wind. Where the API does not
provide wind speed we fall back to a stated calm-conditions constant
(see ``agent``), never silently to zero.
"""

from __future__ import annotations


def convective_coefficient_from_wind(
    wind_speed_m_s: float,
    minimum: float = 5.0,
) -> float:
    """Wind-dependent forced-convection coefficient (W/m²·K).

    h_c = max(minimum, 5.7 + 3.8 u) — the McAdams flat-plate
    correlation with a floor for the still-air limit.
    """
    if wind_speed_m_s < 0.0:
        raise ValueError("wind speed cannot be negative")
    return max(minimum, 5.7 + 3.8 * wind_speed_m_s)