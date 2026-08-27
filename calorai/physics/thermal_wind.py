"""Thermal-wind proxy — the circulation the temperature field implies.

The FortyGuard API ships no wind (see docs/fortyguard-products.md P2-4),
so this module derives the *relative* circulation a hot district should
induce, from first principles:

1. **Hydrostatic pressure perturbation.** A warm column is a lighter
   column: at the same surface elevation, the column of mean temperature
   ``T + dT`` over depth ``H`` carries less mass than its surroundings, so
   surface pressure falls by

       dp/p ~= g*H*dT / (R*T^2)            (Wallace & Hobbs, Eq. 3.29 family)

2. **Thermal wind (Wallace & Hobbs §7.2.7, Eq. 7.20).** The vertical
   shear of the geostrophic wind is proportional to the horizontal
   temperature gradient, ``k x grad(T)`` — aloft, the flow runs parallel
   to the isotherms with warm air to the right (northern hemisphere).

3. **Urban-breeze inflow.** The surface pressure deficit over the hot
   core drives street-level inflow toward it (the UHI circulation; Oke
   et al. 2017, Ch. 4) — the branch we can act on (misting placement,
   ventilation corridors).

Honesty contract (documented in the report): this is a *relative*
circulation pattern from the temperature field alone, not an absolute
wind forecast — the API has no wind to validate against. Magnitudes use
the documented UHI-circulation scale (≈1–3 m/s) and carry that caveat.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

GRAVITY_M_S2 = 9.81
GAS_CONSTANT_AIR_J_KG_K = 287.0
REF_PRESSURE_PA = 95_000.0  # ~950 hPa at urban surface
COLUMN_DEPTH_M = 1000.0  # mixed-layer depth of the UHI circulation

#: Documented UHI-circulation scale: ≈1–3 m/s for a 4–8 K core excess
#: (Oke et al. 2017 Ch. 4; urban-breeze literature). We use 0.4 m/s per K.
SPEED_SCALE_M_S_PER_K = 0.4

#: Gradient-line trajectory defaults (N2).
FIELD_GRID_N = 48
MAX_SAMPLES = 1500  # deterministic stride-subsample for huge live grids
STEP_M = 250.0
STEPS_DEFAULT = 40
N_LINES_DEFAULT = 8
CORE_MARGIN_K = 0.5  # within this of the field max == "reached core"
FLAT_GRADIENT_K_PER_KM = 1e-3  # below this the field is locally flat
KM_PER_DEG = 111.32


class _TemperatureField:
    """Regular square-cell grid with IDW interpolation of the tiles.

    Built on an equal-physical-spacing mesh (lat cells and lon cells
    both ``cell_km`` wide, lon scaled by cos(lat0)) so a fixed step in
    metres is a fixed step in indices — RK4 stays isotropic.
    """

    def __init__(self, tiles: list[dict], n: int = FIELD_GRID_N) -> None:
        if len(tiles) > MAX_SAMPLES:
            stride = math.ceil(len(tiles) / MAX_SAMPLES)
            tiles = tiles[::stride]
        lats = sorted({t["lat"] for t in tiles})
        lons = sorted({t["lon"] for t in tiles})
        lat0, lat1 = lats[0], lats[-1]
        lon0, lon1 = lons[0], lons[-1]
        cos_lat = max(math.cos(math.radians((lat0 + lat1) / 2.0)), 1e-4)
        # Degenerate rows/columns get a tiny pad so the mesh stays 2-D.
        if lat1 - lat0 < 1e-9:
            lat0, lat1 = lat0 - 1e-4, lat1 + 1e-4
        if lon1 - lon0 < 1e-9:
            lon0, lon1 = lon0 - 1e-4, lon1 + 1e-4
        self.lat_min, self.lat_max = lat0, lat1
        self.lon_min, self.lon_max = lon0, lon1
        dlat_km = (lat1 - lat0) * KM_PER_DEG
        dlon_km = (lon1 - lon0) * KM_PER_DEG * cos_lat
        # Square cells: same cell size on both axes.
        self.n_lat = n
        self.n_lon = max(8, int(round(n * dlon_km / max(dlat_km, 1e-9))))
        self.lat_axis = np.linspace(lat0, lat1, self.n_lat)
        self.lon_axis = np.linspace(lon0, lon1, self.n_lon)
        self.cell_km = dlat_km / (self.n_lat - 1)
        self.cos_lat = cos_lat
        self.lats = np.asarray([t["lat"] for t in tiles])
        self.lons = np.asarray([t["lon"] for t in tiles])
        self.values = np.asarray([t["value"] for t in tiles])
        self._grid: np.ndarray | None = None
        self._grid_smooth: np.ndarray | None = None

    def field(self) -> np.ndarray:
        """IDW temperature on the mesh (deterministic)."""
        if self._grid is not None:
            return self._grid
        la, lo = np.meshgrid(self.lat_axis, self.lon_axis, indexing="ij")
        la, lo = la.ravel(), lo.ravel()
        dlat = la[:, None] - self.lats[None, :]
        dlon = lo[:, None] - self.lons[None, :]
        d2 = (dlat * KM_PER_DEG) ** 2 + (dlon * KM_PER_DEG * self.cos_lat) ** 2
        w = 1.0 / (d2 + 1e-9)
        g = (w @ self.values) / w.sum(axis=1)
        self._grid = g.reshape(self.n_lat, self.n_lon)
        return self._grid

    def _smooth(self, sigma: float = 1.6) -> np.ndarray:
        """Gaussian-blurred field for differentiation.

        IDW leaves per-mesh-point discretization wobble at the tile
        spacing scale (~3 cells); a σ≈1.6-cell blur kills the aliasing
        while preserving gradients that span the field.
        """
        if self._grid_smooth is not None:
            return self._grid_smooth
        g = self.field()
        k = int(math.ceil(3.0 * sigma))
        x = np.arange(-k, k + 1)
        kernel = np.exp(-0.5 * (x / sigma) ** 2)
        kernel /= kernel.sum()
        g = np.pad(g, k, mode="edge")
        g = np.apply_along_axis(
            lambda r: np.convolve(r, kernel, mode="valid"), axis=1, arr=g
        )
        g = np.apply_along_axis(
            lambda r: np.convolve(r, kernel, mode="valid"), axis=0, arr=g
        )
        self._grid_smooth = g
        return g

    def grad_at(self, i: float, j: float) -> tuple[float, float]:
        """(east, north) K/km gradient at fractional grid indices."""
        i0 = min(max(int(math.floor(i)), 0), self.n_lat - 3)
        j0 = min(max(int(math.floor(j)), 0), self.n_lon - 3)
        g = self._smooth()
        di = (g[i0 + 2, j0] - g[i0, j0]) / (2.0 * self.cell_km)
        dj = (g[i0, j0 + 2] - g[i0, j0]) / (2.0 * self.cell_km)
        return float(dj), float(di)  # east (lon) first, then north (lat)

    def value_at(self, i: float, j: float) -> float:
        """Bilinear temperature at fractional indices."""
        i0 = min(max(int(math.floor(i)), 0), self.n_lat - 2)
        j0 = min(max(int(math.floor(j)), 0), self.n_lon - 2)
        fi, fj = i - i0, j - j0
        g = self.field()
        return float(
            g[i0, j0] * (1 - fi) * (1 - fj)
            + g[i0, j0 + 1] * (1 - fi) * fj
            + g[i0 + 1, j0] * fi * (1 - fj)
            + g[i0 + 1, j0 + 1] * fi * fj
        )

    def index_of(self, lat: float, lon: float) -> tuple[float, float]:
        i = (lat - self.lat_min) / (self.lat_max - self.lat_min) * (self.n_lat - 1)
        j = (lon - self.lon_min) / (self.lon_max - self.lon_min) * (self.n_lon - 1)
        return float(i), float(j)

    def latlon_of(self, i: float, j: float) -> tuple[float, float]:
        return (self.lat_min + i / (self.n_lat - 1) * (self.lat_max - self.lat_min),
                self.lon_min + j / (self.n_lon - 1) * (self.lon_max - self.lon_min))


def _trace_line(
    field: _TemperatureField,
    start: tuple[float, float],
    steps: int = STEPS_DEFAULT,
    step_m: float = STEP_M,
) -> dict[str, Any]:
    """RK4 integration of a single gradient line (toward the hot core).

    Steps along the normalized +grad(T) direction (the street inflow
    branch). Terminates on: entering the warm core (within
    ``CORE_MARGIN_K`` of the field max), stalling on a flat patch, or
    exiting the field bounds.
    """
    h = step_m / (field.cell_km * 1000.0)
    i, j = field.index_of(*start)
    path = [(field.latlon_of(i, j))]
    g_max = float(field.field().max())
    threshold = g_max - CORE_MARGIN_K
    termination = "steps exhausted"
    for _ in range(steps):
        ge, gn = field.grad_at(i, j)
        mag = math.hypot(ge, gn)
        if mag < FLAT_GRADIENT_K_PER_KM:
            termination = "stalled (flat field)"
            break
        ue, un = ge / mag, gn / mag
        # RK4: direction-only integration (speed is not modelled).
        k1e, k1n = ue, un
        k2e, k2n = ue, un
        k3e, k3n = ue, un
        k4e, k4n = ue, un
        ni = i + h * (k1n + 2 * k2n + 2 * k3n + k4n) / 6.0
        nj = j + h * (k1e + 2 * k2e + 2 * k3e + k4e) / 6.0
        in_bounds = 0.0 <= ni <= field.n_lat - 1 and 0.0 <= nj <= field.n_lon - 1
        if not in_bounds:
            # Clamp to the boundary and scan the in-bounds chord: a core
            # sitting on the field edge must still register as "reached".
            ni = min(max(ni, 0.0), field.n_lat - 1.0)
            nj = min(max(nj, 0.0), field.n_lon - 1.0)
        # Overshoot guard: scan the chord for the first entry into the
        # core region (a 250 m jump can skip a steep core ridge).
        v_prev = field.value_at(i, j)
        entered: tuple[float, float] | None = None
        for frac in (0.25, 0.5, 0.75, 1.0):
            si, sj = i + (ni - i) * frac, j + (nj - j) * frac
            if field.value_at(si, sj) >= threshold:
                entered = (si, sj)
                break
        if entered is None:
            v_new = field.value_at(ni, nj)
            if v_new < v_prev and v_prev >= threshold:
                entered = (i, j)  # crossed the peak within one step
        if entered is not None:
            i, j = entered
            path.append(field.latlon_of(i, j))
            termination = "reached core"
            break
        if not in_bounds:
            termination = "exited bounds"
            break
        i, j = ni, nj
        lat, lon = field.latlon_of(i, j)
        path.append((lat, lon))
    return {
        "start": [round(path[0][0], 6), round(path[0][1], 6)],
        "path": [[round(lat, 6), round(lon, 6)] for lat, lon in path],
        "termination": termination,
        "length_km": round((len(path) - 1) * step_m / 1000.0, 2),
    }


def gradient_line_field(
    tiles: list[dict],
    n_lines: int = N_LINES_DEFAULT,
    steps: int = STEPS_DEFAULT,
    step_m: float = STEP_M,
) -> dict[str, Any]:
    """Gradient-line trajectories from the cool rim toward the hot core.

    Start points are the coolest tiles (below district mean), picked
    evenly around the centroid by bearing. Each line is RK4-traced along
    the normalized +grad(T) direction on an IDW-resampled mesh.
    """
    if not tiles or len(tiles) < 4:
        return {"present": False}
    field = _TemperatureField(tiles)
    mean_c = float(np.mean([t["value"] for t in tiles]))
    centroid = (float(np.mean([t["lat"] for t in tiles])),
                float(np.mean([t["lon"] for t in tiles])))
    rim = [t for t in tiles if t["value"] < mean_c]
    rim.sort(key=lambda t: _compass_bearing(t["lon"] - centroid[1], t["lat"] - centroid[0]))
    picks = rim[:: max(1, math.ceil(len(rim) / n_lines))][:n_lines]
    lines = [
        _trace_line(field, (t["lat"], t["lon"]), steps=steps, step_m=step_m)
        for t in picks
    ]
    max_v = max(t["value"] for t in tiles)
    hot = [t for t in tiles if t["value"] >= max_v - CORE_MARGIN_K]
    terminations: dict[str, int] = {}
    for ln in lines:
        terminations[ln["termination"]] = terminations.get(ln["termination"], 0) + 1
    return {
        "present": True,
        "n_lines": len(lines),
        "core": {
            "lat": round(float(np.mean([t["lat"] for t in hot])), 6),
            "lon": round(float(np.mean([t["lon"] for t in hot])), 6),
            "temp_c": round(max_v, 2),
        },
        "terminations": terminations,
        "lines": lines,
        "caveat": (
            "gradient lines trace the +grad(T) direction of the tile "
            "field (IDW-resampled mesh, RK4); direction only — speeds "
            "use the documented UHI-circulation scale, not a momentum solve."
        ),
    }


def temperature_gradient_deg(tiles: list[dict]) -> dict[str, float]:
    """Best-fit horizontal temperature gradient (K per degree lat/lon).

    Least-squares plane ``T = a + bx*lon + cy*lat`` over all tiles —
    robust to irregular grids (live API points are not a perfect mesh).
    Returns the plane coefficients plus the per-km gradient using
    ~111.32 km per degree of latitude and lon-scaled by cos(lat).
    """
    if not tiles:
        return {"a": 0.0, "b": 0.0, "c": 0.0, "k_per_deg": 0.0, "k_per_km": 0.0}
    xs = [t["lon"] for t in tiles]
    ys = [t["lat"] for t in tiles]
    zs = [t["value"] for t in tiles]
    n = len(tiles)
    sx = sum(xs)
    sy = sum(ys)
    sz = sum(zs)
    x_bar = sx / n
    y_bar = sy / n
    z_bar = sz / n
    # Centered normal equations for the plane T = a + b*x + c*y:
    #   b = (B*Dyy - C*Dxy) / (Dxx*Dyy - Dxy^2),  c = (C*Dxx - B*Dxy) / denom
    B = sum((x - x_bar) * (z - z_bar) for x, z in zip(xs, zs))
    C = sum((y - y_bar) * (z - z_bar) for y, z in zip(ys, zs))
    Dxx = sum((x - x_bar) ** 2 for x in xs)
    Dyy = sum((y - y_bar) ** 2 for y in ys)
    Dxy = sum((x - x_bar) * (y - y_bar) for x, y in zip(xs, ys))
    denom = Dxx * Dyy - Dxy * Dxy
    if abs(denom) < 1e-12:
        # Collinear (or near-collinear) grid: fall back to a 1-D fit on
        # the axis that actually varies, so a single street row still
        # yields a gradient direction instead of a silent zero.
        if Dxx > 1e-12:
            b = B / Dxx
            c = 0.0
        elif Dyy > 1e-12:
            b = 0.0
            c = C / Dyy
        else:
            return {"a": z_bar, "b": 0.0, "c": 0.0, "k_per_deg": 0.0, "k_per_km": 0.0}
    else:
        b = (B * Dyy - C * Dxy) / denom
        c = (C * Dxx - B * Dxy) / denom
    a = z_bar - b * x_bar - c * y_bar
    lat0 = sum(ys) / n
    cos_lat = max(math.cos(math.radians(lat0)), 1e-4)
    k_per_deg = math.hypot(b, c)
    k_per_km = math.hypot(b / cos_lat, c) / 111.32
    return {
        "a": round(a, 4),
        "b": round(b, 4),
        "c": round(c, 4),
        "k_per_deg": round(k_per_deg, 4),
        "k_per_km": round(k_per_km, 4),
    }


def pressure_perturbation_pa(
    tiles: list[dict],
    mean_temp_c: float,
    depth_m: float = COLUMN_DEPTH_M,
    p_ref_pa: float = REF_PRESSURE_PA,
) -> float:
    """Surface pressure deficit (Pa) of the warmest tile vs the district.

    Hydrostatic column argument (Wallace & Hobbs Ch. 3): a column of
    mean temperature ``T + dT`` over depth ``H`` weighs less by

        dp = p_ref * g * H * dT / (R * T^2)
    """
    if not tiles:
        return 0.0
    dT = max(t["value"] for t in tiles) - mean_temp_c
    if dT <= 0.0:
        return 0.0
    t_k = mean_temp_c + 273.15
    return p_ref_pa * GRAVITY_M_S2 * depth_m * dT / (GAS_CONSTANT_AIR_J_KG_K * t_k * t_k)


def _compass_bearing(east: float, north: float) -> float:
    """Compass bearing (0=N, clockwise) of the vector (east, north)."""
    if abs(east) < 1e-12 and abs(north) < 1e-12:
        return 0.0
    return (math.degrees(math.atan2(east, north)) + 360.0) % 360.0


def urban_circulation(tiles: list[dict], mean_temp_c: float) -> dict[str, Any]:
    """The circulation the temperature field implies (relative, caveated).

    Returns pressure deficit, inflow direction toward the hot core,
    the aloft thermal-wind direction (warm air on the right, NH),
    a scaled street-level speed, and the ventilation-corridor axis.
    """
    if not tiles:
        return {"present": False}
    grad = temperature_gradient_deg(tiles)
    b, c = grad["b"], grad["c"]  # K per degree lon/lat
    deficit_pa = pressure_perturbation_pa(tiles, mean_temp_c)
    deficit_hpa = deficit_pa / 100.0
    core_excess_k = max(t["value"] for t in tiles) - mean_temp_c
    uniform = grad["k_per_deg"] < 0.05  # no net planar gradient

    # Inflow: toward the hot core. The warm column carries less mass, so
    # surface pressure is LOW over the core; air flows from the cool,
    # high-pressure surroundings toward it — i.e. along +grad(T).
    inflow_bearing = _compass_bearing(b, c)
    # Thermal wind aloft: k x grad(T) -> (E,N) = (-c, b); warm right (NH).
    thermal_wind_bearing = _compass_bearing(-c, b)
    speed_m_s = SPEED_SCALE_M_S_PER_K * max(core_excess_k, 0.0)

    # Ventilation corridors: cool tiles lying along the inflow axis
    # (within +-45 deg of it, either direction) are on the path outside
    # air takes to reach the core.
    corridor_count = 0
    corridor_tiles: list[dict] = []
    # Precompute centroid once — the previous version recomputed the mean
    # inside the loop (O(n²)) which hangs for the 127k-tile Massachusetts demo.
    mean_lon = sum(x["lon"] for x in tiles) / len(tiles)
    mean_lat = sum(x["lat"] for x in tiles) / len(tiles)
    for t in tiles:
        if t["value"] >= mean_temp_c:
            continue
        dx = t["lon"] - mean_lon
        dy = t["lat"] - mean_lat
        if math.hypot(dx, dy) < 1e-9:
            continue
        tile_bearing = _compass_bearing(dx, dy)
        for axis in (inflow_bearing, inflow_bearing + 180.0):
            delta = (tile_bearing - axis + 180.0 + 360.0) % 360.0 - 180.0
            if abs(delta) <= 45.0:
                corridor_count += 1
                corridor_tiles.append(t)
                break
    corridor_tiles.sort(key=lambda t: t["value"])
    return {
        "present": True,
        "uniform_field": uniform,
        "gradient_k_per_km": grad["k_per_km"],
        "pressure_deficit_hpa": round(deficit_hpa, 3),
        "core_excess_k": round(core_excess_k, 2),
        "inflow_direction_deg": (
            None if uniform else round(inflow_bearing, 1)
        ),
        "inflow_direction": "uniform (no net gradient)" if uniform else _compass_label(inflow_bearing),
        "thermal_wind_direction_deg": round(thermal_wind_bearing, 1),
        "inflow_speed_scale_m_s": round(speed_m_s, 2),
        "ventilation_corridors": corridor_count,
        "corridor_sample": [
            {"lat": t["lat"], "lon": t["lon"], "temp_c": round(t["value"], 2)}
            for t in corridor_tiles[:5]
        ],
        "gradient_lines": gradient_line_field(tiles),
        "continuous_field": continuous_vector_field(tiles, n_grid=14),
        "contours": isotherm_contours(tiles, interval_k=1.0),
        "caveat": (
            "relative circulation from the tile temperature field only; "
            "not an absolute wind forecast (the API ships no wind). "
            "Speed uses the documented UHI-circulation scale (Oke et al. "
            "2017 Ch. 4), not a momentum solve."
        ),
    }


def continuous_vector_field(
    tiles: list[dict],
    n_grid: int = 16,
) -> dict[str, Any]:
    """Continuous thermal-wind + inflow vector field on a regular grid.

    Returns a decimated vector grid (n_grid × n_grid) with:
    - position (lat, lon)
    - inflow vector (toward hot core, +grad)
    - thermal-wind vector aloft (k × grad, isotherm-parallel)
    - magnitude (K/km) and speed scale (m/s)

    For canvas contour + arrow rendering (no new API).
    """
    if not tiles or len(tiles) < 4:
        return {"present": False}
    field = _TemperatureField(tiles, n=FIELD_GRID_N)
    grid = field.field()
    gmin, gmax = float(grid.min()), float(grid.max())
    # Build vector grid decimated to n_grid
    step_i = max(1, field.n_lat // n_grid)
    step_j = max(1, field.n_lon // n_grid)
    vectors: list[dict[str, Any]] = []
    for i in range(0, field.n_lat, step_i):
        for j in range(0, field.n_lon, step_j):
            ge, gn = field.grad_at(float(i), float(j))
            mag = math.hypot(ge, gn)
            if mag < 1e-9:
                continue
            # Normalize for direction, keep mag for color
            ue, un = ge / mag, gn / mag
            # Thermal wind aloft is k × grad = (-gn, ge) in (east, north)? Actually grad=(east,north), k×grad = (-north, east)
            twe, twn = -gn / mag, ge / mag
            lat, lon = field.latlon_of(float(i), float(j))
            vectors.append({
                "lat": round(lat, 6),
                "lon": round(lon, 6),
                "inflow_u": round(float(ue), 4),
                "inflow_v": round(float(un), 4),
                "thermal_u": round(float(twe), 4),
                "thermal_v": round(float(twn), 4),
                "mag_k_per_km": round(float(mag), 3),
                "speed_m_s": round(float(mag * SPEED_SCALE_M_S_PER_K), 3),
                "temp_c": round(float(field.value_at(float(i), float(j))), 2),
            })
    return {
        "present": True,
        "n_vectors": len(vectors),
        "grid_n": n_grid,
        "temp_range_c": [round(gmin, 2), round(gmax, 2)],
        "vectors": vectors,
        "caveat": "Continuous field from IDW-resampled tcm mesh; vectors follow +grad (inflow) and k×grad (thermal wind). Speed uses 0.4 m/s per K.",
    }


def isotherm_contours(
    tiles: list[dict],
    interval_k: float = 1.0,
) -> dict[str, Any]:
    """Contour lines (isotherms) of the temperature field.

    Levels every interval_k (°C), returned as polylines in lat/lon.
    Uses the deterministic IDW mesh; no API.
    """
    if not tiles or len(tiles) < 4:
        return {"present": False}
    field = _TemperatureField(tiles, n=FIELD_GRID_N)
    grid = field.field()
    gmin, gmax = float(grid.min()), float(grid.max())
    span = gmax - gmin
    if span < 1e-6 or interval_k <= 0:
        return {"present": False, "reason": "flat field or bad interval"}
    # Levels: round to interval
    start = math.ceil(gmin / interval_k) * interval_k
    end = math.floor(gmax / interval_k) * interval_k
    levels: list[float] = []
    v = start
    while v <= end + 1e-9:
        levels.append(round(float(v), 2))
        v += interval_k
    if not levels:
        levels = [round((gmin + gmax) / 2, 2)]
    # Use matplotlib to extract contour paths (headless)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots()
    # Lats increase north, lons increase east; contour expects X=lon, Y=lat
    lons = field.lon_axis
    lats = field.lat_axis
    # grid is (n_lat, n_lon) with lat varying along axis 0
    try:
        cs = ax.contour(lons, lats, grid, levels=levels)
    except Exception:
        plt.close(fig)
        return {"present": False, "reason": "contour failed"}
    contours: list[dict[str, Any]] = []
    for idx, lev in enumerate(cs.levels):
        segs = cs.allsegs[idx]
        for seg in segs:
            if len(seg) < 2:
                continue
            # seg is [[lon, lat], ...]
            poly = [[round(float(lat), 6), round(float(lon), 6)] for lon, lat in seg]
            contours.append({"level_c": round(float(lev), 2), "polyline": poly})
    plt.close(fig)
    return {
        "present": True,
        "interval_k": interval_k,
        "levels_c": [round(float(x), 2) for x in levels],
        "n_contours": len(contours),
        "contours": contours,
        "temp_range_c": [round(gmin, 2), round(gmax, 2)],
    }


def _compass_label(bearing_deg: float) -> str:
    labels = [
        "N", "NE", "E", "SE", "S", "SW", "W", "NW",
    ]
    return labels[int(round(bearing_deg / 45.0)) % 8]