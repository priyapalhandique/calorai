"""M3 — heat-response action plan from the WBGT band.

A concrete, ordered set of actions a site manager / heat officer can
take at the district's measured WBGT. Mirrors the OSHA-style ladder in
``physics.stress`` but adds *ordered* actions (what first, what scales)
so the responder tool returns a plan, not just a level.
"""

from __future__ import annotations

from typing import Any

ACTIONS: dict[str, list[dict[str, Any]]] = {
    "low": [
        {"action": "Continue normal outdoor work.", "priority": 1},
        {"action": "Provide water at work sites.", "priority": 2},
    ],
    "moderate": [
        {"action": "Mandatory water breaks every 45 min in the shade.", "priority": 1},
        {"action": "Schedule heavy work for the coolest hours.", "priority": 2},
        {"action": "Stand by misting (see responder plan).", "priority": 3},
    ],
    "high": [
        {"action": "Rotate crews: 15 min work / 15 min rest in shade.", "priority": 1},
        {"action": "Activate misting + shaded rest stations.", "priority": 2},
        {"action": "Suspend new heavy outdoor tasks; monitor for heat illness signs.", "priority": 3},
    ],
    "extreme": [
        {"action": "Stop heavy outdoor work; emergency protocol.", "priority": 1},
        {"action": "Move to cooled rest areas; rapid hydration with electrolytes.", "priority": 2},
        {"action": "Monitor workers for heat exhaustion/stroke symptoms continuously.", "priority": 3},
        {"action": "Resume only after WBGT drops below the high band.", "priority": 4},
    ],
}

BAND_HINTS: dict[str, str] = {
    "low": "WBGT below 28 °C — routine operations.",
    "moderate": "WBGT 28-30.9 °C — add hydration and rest cycles.",
    "high": "WBGT 31-32.9 °C — reduce intensity, add rest, enable cooling.",
    "extreme": "WBGT >= 33 °C — stop heavy work; emergency protocol.",
}


def heat_response_plan(wbgt_c: float) -> dict[str, Any]:
    """Ordered action plan for a WBGT value (falls back by band)."""
    from calorai.physics.stress import heat_stress_level

    level = heat_stress_level(wbgt_c)["level"]
    actions = ACTIONS.get(level, ACTIONS["low"])
    return {
        "wbgt_c": round(wbgt_c, 2),
        "band": level,
        "hint": BAND_HINTS.get(level, ""),
        "actions": actions,
        "source": "OSHA-style WBGT ladder (calorai physics.stress) + operational orderings",
    }