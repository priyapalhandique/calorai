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
from .canyon import (
    canyon_albedo,
    canyon_longwave_environment_c,
    sky_view_factor,
)
from .convection import convective_coefficient_from_wind
from .inertia import (
    cooling_curve_temperature,
    damping_depth_m,
    diurnal_phase_lag_hours,
    overnight_retention_ratio,
    slab_time_constant,
    storage_heat_flux_force_restore,
    thermal_admittance,
    thermal_effusivity,
    time_to_cool,
)
from .latent import (
    priestley_taylor_latent_flux,
    psychrometric_constant_kpa,
    saturation_vapor_pressure_kpa,
    saturation_vapor_pressure_slope_kpa_k,
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
from .sensitivity import (
    EquilibriumInputs,
    equilibrium_surface_temperature_c,
    sensitivity_bands,
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
    "EquilibriumInputs",
    "MATERIALS",
    "SOLAR_CONSTANT",
    "SurfaceBudget",
    "WBGT_BANDS",
    "absorbed_solar_flux",
    "albedo_delta_temperature",
    "canyon_albedo",
    "canyon_longwave_environment_c",
    "celsius_to_fahrenheit",
    "celsius_to_kelvin",
    "clear_sky_emissivity",
    "closure_analysis",
    "convective_coefficient_from_wind",
    "convective_flux",
    "cooling_curve_temperature",
    "damping_depth_m",
    "diurnal_phase_lag_hours",
    "energy_balance",
    "equilibrium_surface_temperature_c",
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
    "priestley_taylor_latent_flux",
    "psychrometric_constant_kpa",
    "radiative_conductance",
    "saturation_vapor_pressure_kpa",
    "saturation_vapor_pressure_slope_kpa_k",
    "sensitivity_bands",
    "shade_delta_temperature",
    "sky_temperature_c",
    "sky_view_factor",
    "slab_time_constant",
    "solar_declination_degrees",
    "solar_elevation_degrees",
    "stefan_boltzmann_surface_temperature",
    "storage_capacity",
    "storage_flux",
    "storage_heat_flux_force_restore",
    "temperature_drop_from_flux_removal",
    "thermal_admittance",
    "thermal_effusivity",
    "tilted_incident_irradiance",
    "time_to_cool",
    "wbgt",
]