"""calorai physics — deterministic thermodynamics core.

Pure functions only: no I/O, no network, fully unit-testable.
"""

from .budget import (
    SurfaceBudget,
    convective_flux,
    energy_balance,
    linearized_conductance,
    storage_capacity,
    storage_flux,
)
from .inertia import (
    cooling_curve_temperature,
    overnight_retention_ratio,
    slab_time_constant,
    thermal_effusivity,
    time_to_cool,
)
from .mitigation import (
    MATERIALS,
    albedo_delta_temperature,
    heat_capacity_delta_peak_temperature,
    shade_delta_temperature,
    temperature_drop_from_flux_removal,
)
from .radiation import (
    absorbed_solar_flux,
    net_longwave_flux,
    radiative_conductance,
    stefan_boltzmann_surface_temperature,
)
from .stress import (
    WBGT_BANDS,
    exposure_risk,
    heat_stress_level,
    wbgt,
)
from .units import (
    celsius_to_fahrenheit,
    celsius_to_kelvin,
    fahrenheit_to_celsius,
    normalize_celsius,
)

__all__ = [
    "MATERIALS",
    "SurfaceBudget",
    "WBGT_BANDS",
    "absorbed_solar_flux",
    "albedo_delta_temperature",
    "celsius_to_fahrenheit",
    "celsius_to_kelvin",
    "convective_flux",
    "cooling_curve_temperature",
    "energy_balance",
    "exposure_risk",
    "fahrenheit_to_celsius",
    "heat_capacity_delta_peak_temperature",
    "heat_stress_level",
    "linearized_conductance",
    "net_longwave_flux",
    "normalize_celsius",
    "overnight_retention_ratio",
    "radiative_conductance",
    "shade_delta_temperature",
    "slab_time_constant",
    "stefan_boltzmann_surface_temperature",
    "storage_capacity",
    "storage_flux",
    "temperature_drop_from_flux_removal",
    "thermal_effusivity",
    "time_to_cool",
    "wbgt",
]