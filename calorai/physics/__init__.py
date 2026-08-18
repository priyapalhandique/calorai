"""calorai physics — deterministic thermodynamics core.

Pure functions only: no I/O, no network, fully unit-testable.
"""

from .budget import (
    SurfaceBudget,
    closure_analysis,
    convective_flux,
    energy_balance,
    implied_convective_coefficient,
    linearized_conductance,
    storage_capacity,
    storage_flux,
)
from .convection import convective_coefficient_from_wind
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
    SOLAR_CONSTANT,
    absorbed_solar_flux,
    clear_sky_emissivity,
    net_longwave_flux,
    radiative_conductance,
    sky_temperature_c,
    stefan_boltzmann_surface_temperature,
)
from .solar import (
    hour_angle_degrees,
    solar_declination_degrees,
    solar_elevation_degrees,
    tilted_incident_irradiance,
)
from .stress import (
    WBGT_BANDS,
    exposure_risk,
    globe_temperature_c,
    heat_exposure_dose,
    heat_stress_level,
    humidex,
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
    "SOLAR_CONSTANT",
    "SurfaceBudget",
    "WBGT_BANDS",
    "absorbed_solar_flux",
    "albedo_delta_temperature",
    "celsius_to_fahrenheit",
    "celsius_to_kelvin",
    "clear_sky_emissivity",
    "closure_analysis",
    "convective_coefficient_from_wind",
    "convective_flux",
    "cooling_curve_temperature",
    "energy_balance",
    "exposure_risk",
    "fahrenheit_to_celsius",
    "globe_temperature_c",
    "heat_capacity_delta_peak_temperature",
    "heat_exposure_dose",
    "heat_stress_level",
    "hour_angle_degrees",
    "humidex",
    "implied_convective_coefficient",
    "linearized_conductance",
    "net_longwave_flux",
    "normalize_celsius",
    "overnight_retention_ratio",
    "radiative_conductance",
    "shade_delta_temperature",
    "sky_temperature_c",
    "slab_time_constant",
    "solar_declination_degrees",
    "solar_elevation_degrees",
    "stefan_boltzmann_surface_temperature",
    "storage_capacity",
    "storage_flux",
    "temperature_drop_from_flux_removal",
    "thermal_effusivity",
    "tilted_incident_irradiance",
    "time_to_cool",
    "wbgt",
]