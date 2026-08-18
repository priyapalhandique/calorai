"""Semantics-free unit helpers shared across the physics modules.

The FortyGuard API returns Celsius throughout, but the heatmap tile
layer has historically mixed units — we detect and normalize defensively
rather than trust the label.
"""

from __future__ import annotations


def fahrenheit_to_celsius(value: float) -> float:
    """Convert degrees Fahrenheit to Celsius."""
    return (value - 32.0) * 5.0 / 9.0


def celsius_to_fahrenheit(value: float) -> float:
    """Convert degrees Celsius to Fahrenheit."""
    return value * 9.0 / 5.0 + 32.0


def celsius_to_kelvin(value: float) -> float:
    """Convert degrees Celsius to kelvin (K = C + 273.15)."""
    return value + 273.15


def normalize_celsius(value: float) -> float:
    """Heuristically normalize a temperature to Celsius.

    Values above 60 °C are almost certainly °F readings (the API has
    historically returned °F in `tcm` tiles); everything else is treated
    as °C. 60 °C = 140 °F, far beyond any recorded surface-air anchor.
    """
    if value > 60.0:
        return fahrenheit_to_celsius(value)
    return value


def celsius_delta_from_fahrenheit_delta(value: float) -> float:
    """Convert a temperature *difference* from °F to °C (5/9 scaling)."""
    return value * 5.0 / 9.0