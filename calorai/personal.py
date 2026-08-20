"""Personal intelligence layer (D8) — user profile + personalization.

No accounts, no auth: a *demo persona* travels with each request as a
small JSON profile. The planner personalizes the spoken summary
(``answer_tldr``) with the profile's units and work intensity, and
prefers the profile's threshold and home district as fallbacks when
the query names nothing. No personal data is stored server-side;
recent-query context lives in the ``AgentContext`` for follow-up
resolution ("it", "that", "its").

Deep memory (saved query history) is deliberately out of scope per the
project plan — preferences only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

UNITS = ("c", "f")
INTENSITIES = ("light", "moderate", "heavy")

_INTENSITY_LABEL = {
    "light": "light",
    "moderate": "moderate",
    "heavy": "heavy",
}


@dataclass
class UserProfile:
    """Demo persona sent by the client with each request."""

    units: str = "c"
    intensity: str = "moderate"
    threshold_c: float | None = None
    home_district: str | None = None
    voice: bool = field(default=False)

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> "UserProfile":
        """Parse a client profile dict; every invalid field falls back."""
        raw = raw or {}
        units = str(raw.get("units", "c")).lower()
        if units not in UNITS:
            units = "c"
        intensity = str(raw.get("intensity", "moderate")).lower()
        if intensity not in INTENSITIES:
            intensity = "moderate"
        threshold = raw.get("threshold_c")
        if threshold is None:
            threshold_c = None
        else:
            try:
                threshold_c = float(threshold)
            except (TypeError, ValueError):
                threshold_c = None
        home = str(raw.get("home_district") or "").strip()
        return cls(
            units=units,
            intensity=intensity,
            threshold_c=threshold_c,
            home_district=home or None,
            voice=bool(raw.get("voice", False)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "units": self.units,
            "intensity": self.intensity,
            "threshold_c": self.threshold_c,
            "home_district": self.home_district,
            "voice": self.voice,
        }


def c_to_f(c: float) -> float:
    """Celsius -> Fahrenheit."""
    return c * 9.0 / 5.0 + 32.0


def format_temp(c: float, units: str) -> str:
    """Absolute temperature in the profile's units ("41.2 °C"/"106.2 °F")."""
    if units == "f":
        return f"{c_to_f(c):.1f} °F"
    return f"{c:.1f} °C"


def format_temp_pair(c: float, units: str) -> str:
    """Absolute temperature with the alternate unit in parentheses."""
    if units == "f":
        return f"{c_to_f(c):.1f} °F ({c:.1f} °C)"
    return f"{c:.1f} °C ({c_to_f(c):.1f} °F)"


def intensity_label(intensity: str) -> str:
    return _INTENSITY_LABEL.get(intensity, "moderate")