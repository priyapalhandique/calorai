"""Facade-orientation advisor — Track 2 (Future Buildings & Energy).

Scores how a building's vertical walls and roof are exposed to solar
load through the day, so glazing choices and HVAC sizing follow the
*orientation-specific* thermal load instead of a blanket rule.

The instantaneous load on a vertical wall facing azimuth ψ (0=N, 90=E,
180=S, 270=W) is the beam projection onto the wall plane:

    G_wall = (1 − k_d)·GHI·max(cos el · cos(az − ψ), 0) / sin el
             + k_d·GHI/2 + ρ_g·GHI/2        (isotropic diffuse + ground)

i.e. the tilted-plane model (``tilted_incident_irradiance``) at
tilt = 90°. When only a daily clear-sky scalar is available, hourly
GHI is reconstructed as S₀·sin(el)·τ (τ = 0.75 clear-sky) so the
*ranking* of orientations is stable; absolute numbers carry the
clear-sky caveat.
"""

from __future__ import annotations

from .solar import (
    clear_sky_ghi_w_m2,
    hour_angle_degrees,
    solar_azimuth_degrees,
    solar_declination_degrees,
    solar_elevation_degrees,
    tilted_incident_irradiance,
)

#: Cardinal wall azimuths, from North clockwise.
WALL_AZIMUTHS = {
    "north": 0.0,
    "east": 90.0,
    "south": 180.0,
    "west": 270.0,
}


def facade_hourly_flux_w_m2(
    latitude_deg: float,
    longitude_deg: float,
    day_of_year: int,
    clock_hour: float,
    utc_offset_hours: float,
    wall_azimuth_deg: float,
    ground_albedo: float = 0.20,
    transmittance: float = 0.75,
) -> dict:
    """Instantaneous incident flux (W/m²) on a vertical wall.

    Returns the decomposed beam/diffuse/reflected split plus the sun
    position, or None-fluxes when the sun is below the horizon.
    """
    decl = solar_declination_degrees(day_of_year)
    h = hour_angle_degrees(clock_hour, utc_offset_hours, longitude_deg)
    elev = solar_elevation_degrees(latitude_deg, decl, h)
    az = solar_azimuth_degrees(latitude_deg, decl, h, elev)
    if elev <= 0.0:
        return {
            "clock_hour": clock_hour,
            "elevation_deg": round(elev, 2),
            "azimuth_deg": round(az, 2),
            "incident_w_m2": 0.0,
            "beam_w_m2": 0.0,
            "diffuse_w_m2": 0.0,
            "reflected_w_m2": 0.0,
        }
    ghi = clear_sky_ghi_w_m2(elev, transmittance)
    tilted = tilted_incident_irradiance(
        ghi,
        elev,
        tilt_deg=90.0,
        surface_azimuth_deg=wall_azimuth_deg,
        solar_azimuth_deg=az,
        ground_albedo=ground_albedo,
    )
    return {
        "clock_hour": clock_hour,
        "elevation_deg": round(elev, 2),
        "azimuth_deg": round(az, 2),
        "incident_w_m2": tilted["incident_w_m2"],
        "beam_w_m2": tilted["beam_w_m2"],
        "diffuse_w_m2": tilted["diffuse_w_m2"],
        "reflected_w_m2": tilted["reflected_w_m2"],
    }


def facade_solar_load_kwh_m2_per_day(
    latitude_deg: float,
    longitude_deg: float,
    day_of_year: int,
    utc_offset_hours: float,
    wall_azimuth_deg: float,
    ground_albedo: float = 0.20,
    transmittance: float = 0.75,
) -> dict:
    """Daily solar load (kWh/m²) on a vertical wall, integrated hourly.

    Also reports the peak-hour flux and the hours the wall is in
    direct sun — the two numbers a glazing spec sheet needs.
    """
    total_kwh = 0.0
    peak = {"hour": None, "incident_w_m2": 0.0}
    sunlit_hours = 0.0
    for hour in range(0, 24):
        flux = facade_hourly_flux_w_m2(
            latitude_deg,
            longitude_deg,
            day_of_year,
            hour,
            utc_offset_hours,
            wall_azimuth_deg,
            ground_albedo,
            transmittance,
        )
        total_kwh += flux["incident_w_m2"] / 1000.0
        if flux["beam_w_m2"] > 1.0:
            sunlit_hours += 1.0
        if flux["incident_w_m2"] > peak["incident_w_m2"]:
            peak = {"hour": hour, "incident_w_m2": flux["incident_w_m2"]}
    return {
        "azimuth_deg": wall_azimuth_deg,
        "load_kwh_m2_per_day": round(total_kwh, 2),
        "peak_hour": peak["hour"],
        "peak_flux_w_m2": round(peak["incident_w_m2"], 1),
        "direct_sun_hours": sunlit_hours,
    }


def facade_heat_load_ranking(
    latitude_deg: float,
    longitude_deg: float,
    day_of_year: int,
    utc_offset_hours: float,
    ground_albedo: float = 0.20,
    transmittance: float = 0.75,
) -> dict:
    """Rank the cardinal facades + roof by daily solar load (kWh/m²).

    Roof is the horizontal plane (tilt = 0 → GHI). Highest load is
    the orientation to de-glaze or shade first.
    """
    results = []
    for name, az in WALL_AZIMUTHS.items():
        results.append(
            {
                "orientation": name,
                **facade_solar_load_kwh_m2_per_day(
                    latitude_deg,
                    longitude_deg,
                    day_of_year,
                    utc_offset_hours,
                    az,
                    ground_albedo,
                    transmittance,
                ),
            }
        )
    roof_kwh = 0.0
    roof_peak = 0.0
    for hour in range(0, 24):
        decl = solar_declination_degrees(day_of_year)
        h = hour_angle_degrees(hour, utc_offset_hours, longitude_deg)
        elev = solar_elevation_degrees(latitude_deg, decl, h)
        if elev > 0.0:
            ghi = clear_sky_ghi_w_m2(elev, transmittance)
            roof_kwh += ghi / 1000.0
            roof_peak = max(roof_peak, ghi)
    results.append(
        {
            "orientation": "roof",
            "azimuth_deg": None,
            "load_kwh_m2_per_day": round(roof_kwh, 2),
            "peak_hour": None,
            "peak_flux_w_m2": round(roof_peak, 1),
            "direct_sun_hours": round(roof_kwh * 1000.0 / max(roof_peak, 1.0), 1),
        }
    )
    results.sort(key=lambda r: r["load_kwh_m2_per_day"], reverse=True)
    return {
        "latitude_deg": latitude_deg,
        "longitude_deg": longitude_deg,
        "day_of_year": day_of_year,
        "utc_offset_hours": utc_offset_hours,
        "ranking": results,
        "hottest": results[0]["orientation"] if results else None,
        "coolest": results[-1]["orientation"] if results else None,
    }