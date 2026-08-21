"""PDF report builder — a judge-ready artifact from the audit dict.

Builds a structured "Urban Heat Budget Audit" PDF with a real table of
contents, tables, and matplotlib figures, entirely from the
deterministic report (``AuditAgent.run()``). No API credits, no
premium dependency: the same numbers the web UI shows, in a printable
deliverable.

Layout:
    Cover → TOC → Snapshot → Energy attribution (+ charts) → Canyon →
    Inertia (+ diurnal chart) → Exposure → Interventions + retrofit
    ROI (+ ΔT chart) → Vulnerability (+ score donut) → Facade advisor
    (+ chart) → Equity & cost (+ circulation/productivity/downburst
    charts) → Theory-vs-data → Provenance & warnings

Figures:
    A. energy-balance flux bars         F. vulnerability component donut
    B. cause-attribution donut          G. circulation vector diagram
    C. diurnal T/solar twin-axis chart  H. WBGT work-capacity curves
    D. facade daily-load bars           I. downburst depression series
    E. intervention ΔT bars             J. tile distribution + normal fit
                                        K. hourly tile-spread boxplots
                                        L. radial UHI cross-section
"""

from __future__ import annotations

import html
import io
import math
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")  # headless: charts are rendered to PNG, never a GUI
import matplotlib.pyplot as plt
import numpy as np

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
    Image,
)

from .analyst.statistics import fig_histogram_normal, fig_hourly_boxplot, fig_radial_uhi

NAVY = colors.HexColor("#16283f")
ACCENT = colors.HexColor("#c2600a")
LIGHT = colors.HexColor("#eef2f6")
GRID = colors.HexColor("#c9d2dc")

OUTPUTS_DIR = Path("outputs")

_MPL_NAVY = "#16283f"
_MPL_ACCENT = "#c2600a"

_PALETTE = ["#16283f", "#c2600a", "#4a7a5a", "#7a8aa0", "#8a5a30", "#9a5a8a"]


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "H1": ParagraphStyle(
            "CaloraiH1",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=15,
            textColor=NAVY,
            spaceBefore=14,
            spaceAfter=6,
            keepWithNext=True,
        ),
        "H2": ParagraphStyle(
            "CaloraiH2",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11.5,
            textColor=ACCENT,
            spaceBefore=10,
            spaceAfter=4,
            keepWithNext=True,
        ),
        "Body": ParagraphStyle(
            "CaloraiBody",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13,
            textColor=colors.HexColor("#22303f"),
        ),
        "Small": ParagraphStyle(
            "CaloraiSmall",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#5a6a7a"),
        ),
        "CoverTitle": ParagraphStyle(
            "CoverTitle",
            fontName="Helvetica-Bold",
            fontSize=26,
            leading=32,
            textColor=NAVY,
            alignment=TA_CENTER,
        ),
        "CoverSub": ParagraphStyle(
            "CoverSub",
            fontName="Helvetica",
            fontSize=12,
            leading=17,
            textColor=colors.HexColor("#33475c"),
            alignment=TA_CENTER,
        ),
        "TOCEntry": ParagraphStyle(
            "CaloraiTOC",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=15,
        ),
    }


def _p(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(html.escape(str(text)), style)


def _kv_table(rows: list[tuple[str, Any]], widths: tuple[float, float] = (6.2 * cm, 9.3 * cm)) -> Table:
    data = [[_p(k, _styles()["Body"]), _p(v, _styles()["Body"])] for k, v in rows]
    table = Table(data, colWidths=widths, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), LIGHT),
                ("TEXTCOLOR", (0, 0), (0, -1), NAVY),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.4, GRID),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


# ------------------------------------------------------------------ charts


def _image_from_fig(fig: Any, width: float = 15.5 * cm) -> Image:
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110)
    plt.close(fig)
    buf.seek(0)
    height = width * (fig.get_size_inches()[1] / fig.get_size_inches()[0])
    return Image(buf, width=width, height=height)


def _energy_chart(attr: dict[str, Any]) -> Image:

    labels = ["Solar absorbed", "Net longwave", "Convection", "Storage", "Latent"]
    values = [
        attr.get("solar_flux", 0.0),
        abs(attr.get("longwave_flux", 0.0)),
        abs(attr.get("convection_flux", 0.0)),
        attr.get("storage_flux", 0.0),
        abs(attr.get("latent_flux", 0.0)),
    ]
    fig, ax = plt.subplots(figsize=(5.4, 2.4))
    ax.barh(labels, values, color=_PALETTE[: len(labels)])
    ax.invert_yaxis()
    ax.set_title("A · Energy balance at the audit hour (W/m²)", fontsize=9, color=_MPL_NAVY)
    ax.tick_params(labelsize=8)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    return _image_from_fig(fig)


def _attribution_donut(attr: dict[str, Any]) -> Image:

    shares = {
        "Solar absorption": max(0.0, attr.get("solar_share", 0.0)),
        "Longwave retention": max(0.0, attr.get("longwave_share", 0.0)),
        "Convection suppression": max(0.0, attr.get("convection_share", 0.0)),
    }
    fig, ax = plt.subplots(figsize=(3.6, 2.6))
    ax.pie(
        list(shares.values()),
        labels=list(shares.keys()),
        colors=_PALETTE[: len(shares)],
        autopct="%1.0f%%",
        startangle=90,
        wedgeprops=dict(width=0.42, edgecolor="white"),
        textprops={"fontsize": 8},
    )
    ax.set_title("B · Cause attribution", fontsize=9, color=_MPL_NAVY)
    return _image_from_fig(fig, width=9.5 * cm)


def _diurnal_chart(diurnal: dict[str, Any], solar_noon_h: float, audit_hour: int) -> Image:

    hours = diurnal.get("hours", list(range(24)))
    apparent = [v if v is not None else float("nan") for v in diurnal.get("apparent_c", [])]
    solar = [v if v is not None else 0.0 for v in diurnal.get("solar_w_m2", [])]
    fig, ax = plt.subplots(figsize=(5.4, 2.7))
    if solar:
        ax.bar(hours, solar, width=0.9, color="#d9c9b3", label="Solar (W/m², right)")
        ax.set_ylabel("W/m²", fontsize=8)
    if apparent:
        ax.plot(hours, apparent, "-o", color=_MPL_ACCENT, markersize=3, label="Apparent temp (°C)")
        ax.set_ylabel("°C", fontsize=8)
        ax.set_xlabel("Hour (local)", fontsize=8)
    ax.axvline(solar_noon_h, color=_MPL_NAVY, ls="--", lw=1, label=f"Solar noon {solar_noon_h:.1f}h")
    ax.axvline(audit_hour, color="#8a5a30", ls=":", lw=1.2, label=f"Audit hour {audit_hour}h")
    ax.set_title("C · Diurnal apparent temperature & solar load", fontsize=9, color=_MPL_NAVY)
    ax.tick_params(labelsize=7.5)
    ax.legend(fontsize=7, loc="upper left")
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    return _image_from_fig(fig)


def _facade_chart(ranking: list[dict[str, Any]]) -> Image:

    order = sorted(ranking, key=lambda r: r.get("load_kwh_m2_per_day", 0.0))
    labels = [r.get("orientation", "?") for r in order]
    values = [r.get("load_kwh_m2_per_day", 0.0) for r in order]
    fig, ax = plt.subplots(figsize=(5.4, 2.2))
    ax.barh(labels, values, color=_PALETTE[: len(labels)])
    ax.invert_yaxis()
    ax.set_xlabel("kWh/m² per day", fontsize=8)
    ax.set_title("D · Facade daily solar load by orientation", fontsize=9, color=_MPL_NAVY)
    ax.tick_params(labelsize=8)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    return _image_from_fig(fig)


def _interventions_chart(interventions: list[dict[str, Any]]) -> Image:

    names = [iv.get("name", "?") for iv in interventions]
    deltas = [iv.get("delta_t_c", 0.0) for iv in interventions]
    short = [n.split("(")[0].strip() for n in names]
    fig, ax = plt.subplots(figsize=(5.4, 2.4))
    bars = ax.barh(short, deltas, color=_PALETTE[: len(deltas)])
    ax.bar_label(bars, fmt="%.1f °C", fontsize=7.5, padding=3)
    ax.invert_yaxis()
    ax.set_xlabel("Peak cooling (°C)", fontsize=8)
    ax.set_title("E · Intervention impact on peak surface temperature", fontsize=9, color=_MPL_NAVY)
    ax.tick_params(labelsize=8)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    return _image_from_fig(fig)


def _vulnerability_donut(components: dict[str, Any]) -> Image:

    fig, ax = plt.subplots(figsize=(3.6, 2.6))
    labels = [k.replace("_points", "").capitalize() for k in components]
    ax.pie(
        list(components.values()),
        labels=labels,
        colors=_PALETTE[: len(components)],
        autopct="%1.0f",
        startangle=90,
        wedgeprops=dict(width=0.42, edgecolor="white"),
        textprops={"fontsize": 8},
    )
    ax.set_title("F · Vulnerability score components (pts of 100)", fontsize=9, color=_MPL_NAVY)
    return _image_from_fig(fig, width=9.5 * cm)


def _circulation_diagram(circ: dict[str, Any]) -> Image:
    """G · the circulation the temperature field implies.

    A small vector diagram: inflow toward the hot core at street level
    (from the hydrostatic pressure deficit), and the aloft thermal wind
    running perpendicular to the temperature gradient (Wallace & Hobbs
    §7.2.7, Eq. 7.20) — warm air on the right (northern hemisphere).
    """
    fig, ax = plt.subplots(figsize=(4.6, 3.4))
    ax.set_xlim(-1.5, 1.5)
    ax.set_ylim(-1.5, 1.5)
    ax.set_aspect("equal")
    ax.axis("off")
    core = (0.0, 0.0)
    ax.plot(*core, "o", ms=16, color=_MPL_ACCENT, zorder=3)
    ax.annotate(
        "hot core\n(>district mean)",
        core,
        xytext=(0.12, 0.12),
        fontsize=7.5,
        color=_MPL_NAVY,
    )

    inflow = circ.get("inflow_direction_deg")
    tw = math.radians(float(circ.get("thermal_wind_direction_deg", 0.0)))
    # inflow: from the rim toward the core (opposite of its bearing vector)
    if inflow is not None:
        inflow = math.radians(float(inflow))
        tip = (0.9 * math.sin(inflow), 0.9 * math.cos(inflow))
        ax.annotate(
            "",
            xy=core,
            xytext=tip,
            arrowprops=dict(arrowstyle="-|>", color=_MPL_NAVY, lw=2.2),
        )
        ax.annotate(
            f"street inflow  {circ.get('inflow_direction', '')} "
            f"({circ.get('inflow_direction_deg', '')}°)\n"
            f"~{circ.get('inflow_speed_scale_m_s', 0.0)} m/s scale",
            tip,
            xytext=(0.15, -1.15),
            fontsize=7.5,
            color=_MPL_NAVY,
            ha="left",
        )
    else:
        ax.annotate(
            "uniform field:\nno net inflow axis",
            (0.4, -1.0),
            xytext=(-1.3, -1.0),
            fontsize=7.5,
            color="#5a6a7a",
        )
    # thermal wind aloft: runs from the diagram edge, perpendicular branch
    tw_tip = (1.1 * math.sin(tw), 1.1 * math.cos(tw))
    ax.annotate(
        "",
        xy=(0.6 * math.sin(tw), 0.6 * math.cos(tw)),
        xytext=tw_tip,
        arrowprops=dict(arrowstyle="-|>", color="#4a7a5a", lw=2.2, ls="--"),
    )
    ax.annotate(
        f"aloft thermal wind {int(circ.get('thermal_wind_direction_deg', 0.0))}°\n"
        "(W&H Eq. 7.20; warm air to the right, NH)",
        tw_tip,
        xytext=(-1.45, 1.05),
        fontsize=7,
        color="#4a7a5a",
    )
    # gradient-line trajectories (N2): real paths traced along +grad(T)
    gl = circ.get("gradient_lines") or {}
    lines = gl.get("lines") or []
    if lines:
        pts = [p for ln in lines for p in ln["path"]]
        lat0 = float(np.mean([p[0] for p in pts]))
        lon0 = float(np.mean([p[1] for p in pts]))
        dlat = max(abs(p[0] - lat0) for p in pts)
        dlon = max(abs(p[1] - lon0) for p in pts)
        scale = max(dlat, dlon, 1e-9)
        for ln in lines:
            path = ln["path"]
            xs = [(p[1] - lon0) / scale for p in path]
            ys = [(p[0] - lat0) / scale for p in path]
            term = ln.get("termination", "")
            color = "#4a7a5a" if term == "exited bounds" else (
                "#c2600a" if term == "reached core" else "#7a8aa0"
            )
            ax.plot(xs, ys, color=color, lw=1.1, alpha=0.8, zorder=2)
            ax.plot(xs[0], ys[0], "o", ms=3, color=color, zorder=2)
            if len(xs) > 1:
                ax.annotate(
                    "",
                    xy=(xs[-1], ys[-1]),
                    xytext=(xs[-2], ys[-2]),
                    arrowprops=dict(arrowstyle="-|>", color=color, lw=1.1, mutation_scale=7),
                )
        ax.annotate(
            f"{len(lines)} gradient lines (RK4 along +grad T)\n"
            f"core {gl.get('core', {}).get('temp_c', '')} °C",
            (-1.45, -1.35),
            fontsize=7,
            color="#5a6a7a",
        )
    ax.set_title(
        "G · Circulation the temperature field implies\n"
        f"grad {circ.get('gradient_k_per_km', 0.0)} K/km · "
        f"Δp {circ.get('pressure_deficit_hpa', 0.0)} hPa · "
        f"{circ.get('ventilation_corridors', 0)} ventilation corridors",
        fontsize=8.5,
        color=_MPL_NAVY,
    )
    return _image_from_fig(fig, width=12.5 * cm)


def _productivity_chart(prod: dict[str, Any]) -> Image:
    """H · WBGT → work-capacity loss for the three work intensities."""

    def curve(points: list[dict[str, float]]) -> tuple[list[float], list[float]]:
        return ([p["wbgt_c"] for p in points], [p["loss_pct"] for p in points])

    fig, ax = plt.subplots(figsize=(5.4, 2.6))
    for i, intensity in enumerate(["light", "moderate", "heavy"]):
        xs, ys = curve(_curve_points(intensity))
        ax.plot(xs, ys, color=_PALETTE[i % len(_PALETTE)], lw=1.8, label=intensity.capitalize())
    wbgt = float(prod.get("wbgt_c", 30.0))
    ax.axvline(wbgt, color=_MPL_ACCENT, ls="--", lw=1, label=f"district WBGT {wbgt:.1f}°C")
    ax.set_xlabel("WBGT (°C)", fontsize=8)
    ax.set_ylabel("Work-capacity loss (%)", fontsize=8)
    ax.set_title(
        "H · Labour-capacity loss at district WBGT (Dunne 2013 / Kjellstrom 2009)",
        fontsize=9,
        color=_MPL_NAVY,
    )
    ax.set_xlim(22, 36)
    ax.set_ylim(0, 45)
    ax.tick_params(labelsize=7.5)
    ax.legend(fontsize=7, loc="upper left")
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    return _image_from_fig(fig)


def _synoptic_chart(syn: dict[str, Any]) -> Image:
    """M · VPD per hour, coloured by fire-weather band."""
    series = syn.get("vpd_series_kpa", []) or []
    if not series:
        return _image_from_fig(plt.figure(figsize=(5.4, 2.2)))
    band = syn.get("fire_band", "low")
    band_color = {"low": "#4a7a5a", "moderate": "#c2600a", "high": "#a02020"}.get(band, "#4a7a5a")
    hours = list(range(len(series)))
    fig, ax = plt.subplots(figsize=(5.4, 2.4))
    ax.bar(hours, series, width=0.85, color=band_color, edgecolor="white", label=f"fire-weather: {band}")
    ax.axhline(2.5, color=_MPL_NAVY, ls=":", lw=0.8, label="moderate \u2265 2.5 kPa")
    ax.axhline(4.0, color=_MPL_NAVY, ls=":", lw=0.8, label="high \u2265 4.0 kPa")
    ax.set_xlabel("Hour (local)", fontsize=8)
    ax.set_ylabel("VPD (kPa)", fontsize=8)
    ax.set_title(f"M \u00b7 Vapor-pressure deficit \u2014 fire-weather band {band}", fontsize=8.5, color=_MPL_NAVY)
    ax.tick_params(labelsize=7.5)
    ax.set_xlim(-0.5, len(series) - 0.5)
    ax.legend(fontsize=7, loc="upper right")
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    return _image_from_fig(fig)


def _downburst_chart(db: dict[str, Any]) -> Image:
    """I · wet-bulb depression per hour, coloured by risk band."""
    series = db.get("series", []) or []
    if not series:
        return _image_from_fig(plt.figure(figsize=(5.4, 2.2)))
    hours = [s["hour"] for s in series]
    dep = [s["depression_k"] for s in series]
    colors_by_risk = {"low": "#4a7a5a", "medium": "#c2600a", "high": "#a02020"}
    fig, ax = plt.subplots(figsize=(5.4, 2.4))
    for s in series:
        ax.bar(
            s["hour"],
            s["depression_k"],
            width=0.85,
            color=colors_by_risk.get(s["risk"], "#4a7a5a"),
            edgecolor="white",
        )
    for th in (8.0, 14.0):
        ax.axhline(th, color=_MPL_NAVY, ls=":", lw=0.8)
    ax.set_xlabel("Hour (local)", fontsize=8)
    ax.set_ylabel("Wet-bulb depression (K)", fontsize=8)
    ax.set_title(
        "I · Downburst thermodynamic diagnostic (Caracena 1990) — "
        f"peak {db.get('peak_risk', 'low')}",
        fontsize=8.5,
        color=_MPL_NAVY,
    )
    ax.tick_params(labelsize=7.5)
    ax.set_xlim(min(hours) - 0.5, max(hours) + 0.5)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    return _image_from_fig(fig)


# ------------------------------------------------------------------ tables


def _interventions_pdf(interventions: list[dict[str, Any]]) -> Table:
    st = _styles()
    rows = [["Rank", "Intervention", "ΔT (°C)", "Removed flux (W/m²)", "Basis", "Scope"]]
    for i, iv in enumerate(interventions, start=1):
        rows.append(
            [
                str(i),
                iv.get("name", ""),
                f'{iv.get("delta_t_c", 0.0):.2f}',
                f'{iv.get("removed_flux_w_m2", 0.0):.0f}',
                iv.get("basis", ""),
                iv.get("scope", ""),
            ]
        )
    data = [[_p(c, st["Body"]) for c in row] for row in rows]
    table = Table(data, colWidths=[1.0 * cm, 4.6 * cm, 1.6 * cm, 2.6 * cm, 4.1 * cm, 1.6 * cm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.4, GRID),
                ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


def _curve_points(intensity: str) -> list[dict[str, float]]:
    from .analyst.productivity import wbgt_curve_points

    return wbgt_curve_points(intensity)


def _fmt(value: Any, suffix: str = "") -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:g}{suffix}"
    return f"{value}{suffix}"


# ------------------------------------------------------------------- story


def _story(report: dict[str, Any]) -> list[Any]:
    st = _styles()
    out: list[Any] = []

    # ------------------------------------------------------------- cover
    out.append(Spacer(1, 3 * cm))
    out.append(_p("Urban Heat Budget Audit", st["CoverTitle"]))
    out.append(Spacer(1, 0.4 * cm))
    out.append(
        _p(
            f"{report.get('district', '')} · {report.get('date', '')} "
            f"· hour {report.get('snapshot', {}).get('hour', '')}:00 local",
            st["CoverSub"],
        )
    )
    out.append(Spacer(1, 0.3 * cm))
    out.append(_p(report.get("one_liner", ""), st["CoverSub"]))
    out.append(Spacer(1, 0.3 * cm))
    out.append(_p(f"Pipeline: {report.get('pipeline', '')}", st["Small"]))
    out.append(_p(f"Data source: {report.get('source', '')}", st["Small"]))
    out.append(PageBreak())

    # ---------------------------------------------------------------- TOC
    out.append(_p("Contents", st["H1"]))
    out.append(_p("(section headings are hyperlinked in the PDF outline)", st["Small"]))
    out.append(Spacer(1, 0.4 * cm))

    snap = report.get("snapshot", {})
    attr = report.get("attribution", {})
    canyon = report.get("canyon", {})
    inertia = report.get("inertia", {})
    exposure = report.get("exposure", {})
    roi = report.get("retrofit_roi", {})
    vuln = report.get("vulnerability", {})
    facade = report.get("facade", {})
    tvd = report.get("theory_vs_data", {})

    # ---------------------------------------------------------- 1 snapshot
    out.append(_p("1. District snapshot", st["H1"]))
    out.append(
        _kv_table(
            [
                ("Tile count", snap.get("n_cells", "—")),
                ("Minimum tile °C", _fmt(snap.get("min_c"))),
                ("Mean tile °C", _fmt(snap.get("mean_c"))),
                ("Maximum tile °C", _fmt(snap.get("max_c"))),
                (
                    "Hottest tile (lat, lon)",
                    f"{snap.get('hottest_tile', {}).get('lat', '—')}, {snap.get('hottest_tile', {}).get('lon', '—')}",
                ),
                ("Hottest tile °C", _fmt(snap.get("hottest_tile", {}).get("value"))),
                ("Exceedance hours above threshold", _fmt(exposure.get("exceedance_hours"))),
            ]
        )
    )
    out.append(Spacer(1, 0.4 * cm))

    # ------------------------------------------------- 2 energy attribution
    out.append(_p("2. Energy attribution at the audit hour", st["H1"]))
    out.append(
        _kv_table(
            [
                ("Absorbed solar flux (W/m²)", _fmt(attr.get("solar_flux"))),
                ("Net longwave flux (W/m²)", _fmt(attr.get("longwave_flux"))),
                ("Convection flux (W/m²)", _fmt(attr.get("convection_flux"))),
                ("Storage flux (W/m²)", _fmt(attr.get("storage_flux"))),
                ("Latent flux (W/m²)", _fmt(attr.get("latent_flux"))),
                ("Net flux (W/m², ~0 at equilibrium)", _fmt(attr.get("net_flux"))),
                ("Equilibrium skin temperature (°C)", _fmt(attr.get("equilibrium_surface_temperature_c"))),
            ]
        )
    )
    out.append(Spacer(1, 0.4 * cm))
    out.append(_energy_chart(attr))
    out.append(Spacer(1, 0.3 * cm))
    out.append(_attribution_donut(attr))
    sens = attr.get("sensitivity", {}) or {}
    if sens:
        out.append(Spacer(1, 0.3 * cm))
        out.append(_p("Sensitivity of the equilibrium temperature (±K)", st["H2"]))
        out.append(
            _kv_table(
                [(k.replace("_", " "), _fmt(v)) for k, v in sorted(sens.items())]
            )
        )
    out.append(Spacer(1, 0.4 * cm))

    # ------------------------------------------------------------ 3 canyon
    out.append(_p("3. Street canyon", st["H1"]))
    out.append(
        _kv_table(
            [
                ("Aspect ratio H/W", canyon.get("aspect_ratio_h_over_w", "—")),
                ("Sky-view factor (mid-street floor)", canyon.get("sky_view_factor", "—")),
                ("Effective albedo (trapping)", canyon.get("effective_albedo", "—")),
                ("Radiative environment (°C)", _fmt(canyon.get("radiative_environment_c"))),
                ("Wind-shelter factor", canyon.get("wind_shelter_factor", "—")),
                ("Street-level h_c (W/m²·K)", canyon.get("street_level_h_c_w_m2k", "—")),
            ]
        )
    )
    out.append(Spacer(1, 0.4 * cm))

    # ------------------------------------------------------------ 4 inertia
    out.append(_p("4. Thermal inertia & diurnal behaviour", st["H1"]))
    out.append(
        _kv_table(
            [
                ("Time constant (h)", _fmt(inertia.get("time_constant_hours"))),
                ("Thermal effusivity (J·m⁻²·K⁻¹·s⁻¹ᐟ²)", _fmt(inertia.get("thermal_effusivity"))),
                ("Thermal admittance", _fmt(inertia.get("thermal_admittance"))),
                ("Damping depth (m)", _fmt(inertia.get("damping_depth_m"))),
                ("Ideal peak lag (h, P/8)", _fmt(inertia.get("ideal_peak_lag_hours"))),
                ("Measured peak lag (h)", _fmt(inertia.get("measured_peak_lag_hours"))),
                ("Solar noon, local (h)", _fmt(inertia.get("solar_noon_local_h"))),
                ("Force-restore storage (W/m²)", _fmt(inertia.get("storage_flux_force_restore_w_m2"))),
                ("Overnight retention ratio", inertia.get("overnight_retention", "—")),
            ]
        )
    )
    diurnal = report.get("diurnal", {}) or {}
    if diurnal.get("apparent_c"):
        out.append(Spacer(1, 0.3 * cm))
        out.append(
            _diurnal_chart(
                diurnal,
                solar_noon_h=float(inertia.get("solar_noon_local_h", 12.0) or 12.0),
                audit_hour=int(snap.get("hour", 14)),
            )
        )
    out.append(Spacer(1, 0.4 * cm))

    # ------------------------------------------------------------ 5 exposure
    out.append(_p("5. Heat exposure", st["H1"]))
    out.append(
        _kv_table(
            [
                ("WBGT (°C)", _fmt(exposure.get("wbgt_c"))),
                ("WBGT band", exposure.get("level", "—")),
                ("Guidance", exposure.get("guidance", "—")),
                ("Humidex (°C)", _fmt(exposure.get("humidex_c"))),
                ("Duration risk", exposure.get("duration_risk", "—")),
                ("Overall risk", exposure.get("overall_risk", "—")),
                ("Cumulative dose (°C·h)", _fmt((exposure.get("dose") or {}).get("wbgt_hours"))),
                (
                    "Dose past very-high band (°C·h)",
                    _fmt((exposure.get("dose") or {}).get("above_threshold_c_hours")),
                ),
            ]
        )
    )
    out.append(Spacer(1, 0.4 * cm))

    # ------------------------------------------- 6 interventions + retrofit ROI
    interventions = report.get("interventions", [])
    out.append(_p("6. Interventions & retrofit economics", st["H1"]))
    out.append(
        _p(
            "Ranked interventions, each with a quantified peak °C from a closed-form lever equation:",
            st["Body"],
        )
    )
    out.append(_interventions_pdf(interventions))
    if interventions:
        out.append(Spacer(1, 0.3 * cm))
        out.append(_interventions_chart(interventions))
    out.append(Spacer(1, 0.5 * cm))
    if roi:
        out.append(_p(f"Top intervention — {roi.get('intervention', '')}", st["H2"]))
        out.append(
            _kv_table(
                [
                    ("Cooling-season degree-hours (°C·h)", _fmt(roi.get("cooling_season_degree_hours_c"))),
                    ("Annual energy avoided (kWh)", _fmt(roi.get("annual_energy_avoided_kwh"))),
                    ("Annual savings (USD)", _fmt(roi.get("annual_savings_usd"))),
                    ("Retrofit cost (USD)", _fmt(roi.get("retrofit_cost_usd"))),
                    ("Simple payback (years)", _fmt(roi.get("payback_years"))),
                    ("Lifespan net savings (USD, 10 yr)", _fmt(roi.get("lifespan_net_savings_usd"))),
                ]
            )
        )
        assumptions = roi.get("assumptions", {}) or {}
        if assumptions:
            out.append(Spacer(1, 0.3 * cm))
            out.append(
                _p(
                    "Assumptions (returned with the numbers, not hidden): "
                    + " · ".join(f"{k.replace('_', ' ')} = {v}" for k, v in assumptions.items()),
                    st["Small"],
                )
            )
    out.append(Spacer(1, 0.4 * cm))

    # -------------------------------------------------------- 7 vulnerability
    out.append(_p("7. Vulnerability & worker safety", st["H1"]))
    score = vuln.get("score", {}) or {}
    alert = vuln.get("safety_alert", {}) or {}
    out.append(
        _kv_table(
            [
                (
                    "Composite vulnerability score (0-100)",
                    f'{score.get("score", "—")} — {score.get("band", "")}',
                ),
                ("Intensity points (WBGT)", _fmt((score.get("components") or {}).get("intensity_points"))),
                ("Duration points (exceedance)", _fmt((score.get("components") or {}).get("duration_points"))),
                ("Sensitivity points (population)", _fmt((score.get("components") or {}).get("sensitivity_points"))),
                ("Dose points (past very-high band)", _fmt((score.get("components") or {}).get("dose_points"))),
                ("Worker alert — WBGT (°C)", _fmt(alert.get("wbgt_c"))),
                ("Worker alert — level", alert.get("level", "—")),
                ("Worker alert — action", alert.get("action", "—")),
            ]
        )
    )
    components = (score.get("components") or {})
    if components:
        out.append(Spacer(1, 0.3 * cm))
        out.append(_vulnerability_donut(components))
    out.append(Spacer(1, 0.4 * cm))

    # ------------------------------------------------------------ 8 facade
    out.append(_p("8. Facade-orientation advisor", st["H1"]))
    out.append(
        _p(
            "Daily solar load per orientation (kWh/m²) — clear-sky reconstruction of the "
            "hourly sun position; seasonality matters (deep summer flips the south facade "
            "to the coldest wall).",
            st["Body"],
        )
    )
    ranking = facade.get("ranking", [])
    if ranking:
        rows = [["Rank", "Orientation", "Load (kWh/m²/day)", "Peak hour", "Peak flux (W/m²)"]]
        for i, r in enumerate(ranking, start=1):
            rows.append(
                [
                    str(i),
                    r.get("orientation", ""),
                    f'{r.get("load_kwh_m2_per_day", 0.0):.2f}',
                    _fmt(r.get("peak_hour")),
                    f'{r.get("peak_flux_w_m2", 0.0):.0f}',
                ]
            )
        data = [[_p(c, st["Body"]) for c in row] for row in rows]
        table = Table(data, colWidths=[1.4 * cm, 3.4 * cm, 3.8 * cm, 2.6 * cm, 4.3 * cm])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.4, GRID),
                    ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        out.append(table)
        out.append(Spacer(1, 0.3 * cm))
        out.append(_facade_chart(ranking))
    out.append(Spacer(1, 0.4 * cm))

    # ------------------------------------------------------ 9 equity & cost
    analysis = report.get("analysis", {}) or {}
    equity = analysis.get("equity", {}) or {}
    productivity = analysis.get("productivity", {}) or {}
    economy = analysis.get("economy", {}) or {}
    circ = report.get("thermal_wind", {}) or {}
    db = report.get("downburst", {}) or {}
    out.append(_p("9. Heat equity, productivity & cost", st["H1"]))
    if equity.get("present"):
        out.append(
            _kv_table(
                [
                    ("Gini coefficient of tile temperatures", _fmt(equity.get("gini"))),
                    (
                        "Quintile gap (°C): hottest 20% vs coolest 20%",
                        _fmt(equity.get("quintile_gap_c")),
                    ),
                    (
                        "Tiles above threshold °C",
                        f'{equity.get("share_above_threshold_pct", "—")}% '
                        f"(threshold {equity.get('threshold_c', '—')} °C)",
                    ),
                    ("Hot-core tiles (within 1 K of max)", f'{equity.get("hot_core_share_pct", "—")}%'),
                    ("Tile field mean / max (°C)", f'{equity.get("mean_c", "—")} / {equity.get("max_c", "—")}'),
                ]
            )
        )
        note = equity.get("note")
        if note:
            out.append(Spacer(1, 0.2 * cm))
            out.append(_p(note, st["Small"]))
    if productivity.get("wbgt_c") is not None:
        out.append(Spacer(1, 0.3 * cm))
        out.append(
            _p(
                f"Labour-capacity loss at district WBGT "
                f"{productivity.get('wbgt_c', '')} °C — moderate work: "
                f"{((productivity.get('moderate') or {}).get('loss_pct'))}% "
                f"({((productivity.get('moderate') or {}).get('usd_per_year'))} USD/yr); "
                f"heavy work: {((productivity.get('heavy') or {}).get('loss_pct'))}%.",
                st["Body"],
            )
        )
        out.append(Spacer(1, 0.2 * cm))
        out.append(_productivity_chart(productivity))
    if economy.get("total_usd_per_year") is not None:
        out.append(Spacer(1, 0.3 * cm))
        out.append(
            _kv_table(
                [
                    ("Cooling energy spend, top intervention (USD/yr)", _fmt(economy.get("cooling_usd_per_year"))),
                    ("Productivity loss (USD/yr)", _fmt(economy.get("productivity_usd_per_year"))),
                    ("District cost of heat, both streams (USD/yr)", _fmt(economy.get("total_usd_per_year"))),
                ]
            )
        )
        assumptions = economy.get("assumptions", {}) or {}
        if assumptions:
            out.append(Spacer(1, 0.2 * cm))
            out.append(
                _p(
                    "Assumptions returned with the numbers: "
                    + "; ".join(f"{k}: {v}" for k, v in assumptions.items()),
                    st["Small"],
                )
            )
    if circ.get("present"):
        out.append(Spacer(1, 0.4 * cm))
        out.append(_p("Circulation the temperature field implies", st["H2"]))
        out.append(
            _kv_table(
                [
                    ("Temperature gradient (K/km)", _fmt(circ.get("gradient_k_per_km"))),
                    ("Core pressure deficit (hPa)", _fmt(circ.get("pressure_deficit_hpa"))),
                    ("Core excess above district mean (K)", _fmt(circ.get("core_excess_k"))),
                    (
                        "Street inflow (toward core)",
                        f'{circ.get("inflow_direction", "—")} '
                        f'({_fmt(circ.get("inflow_direction_deg"))}°)',
                    ),
                    ("Inflow speed scale (m/s)", _fmt(circ.get("inflow_speed_scale_m_s"))),
                    ("Ventilation corridors (cool tiles on inflow axis)", _fmt(circ.get("ventilation_corridors"))),
                ]
            )
        )
        caveat = circ.get("caveat")
        if caveat:
            out.append(Spacer(1, 0.2 * cm))
            out.append(_p(caveat, st["Small"]))
        out.append(Spacer(1, 0.2 * cm))
        out.append(_circulation_diagram(circ))
    if db.get("present"):
        out.append(Spacer(1, 0.4 * cm))
        out.append(_p("Downburst thermodynamic diagnostic", st["H2"]))
        out.append(
            _kv_table(
                [
                    ("Peak wet-bulb depression (K)", _fmt(db.get("peak_depression_k"))),
                    ("Peak risk hour", _fmt(db.get("peak_hour"))),
                    ("Peak risk band", db.get("peak_risk", "—")),
                    ("Hours in medium band", _fmt(db.get("hours_medium"))),
                    ("Hours in high band", _fmt(db.get("hours_high"))),
                ]
            )
        )
        advisory = db.get("advisory")
        caveat = db.get("caveat")
        if advisory:
            out.append(Spacer(1, 0.2 * cm))
            out.append(_p(advisory, st["Body"]))
        if caveat:
            out.append(Spacer(1, 0.2 * cm))
            out.append(_p(caveat, st["Small"]))
        out.append(Spacer(1, 0.2 * cm))
        out.append(_downburst_chart(db))
    out.append(Spacer(1, 0.4 * cm))

    # ------------------------------------------- 10 tile distribution & normality
    stats = analysis.get("statistics", {}) or {}
    if stats.get("present"):
        s = stats.get("summary", {}) or {}
        o = stats.get("outliers", {}) or {}
        nm = stats.get("normality", {}) or {}
        uhi = stats.get("radial_uhi", {}) or {}
        out.append(Spacer(1, 0.4 * cm))
        out.append(_p("10. Tile distribution & normality", st["H1"]))
        out.append(
            _kv_table(
                [
                    ("Tiles in field", _fmt(stats.get("n_tiles"))),
                    ("Range (°C)", f'{s.get("min_c", "—")} … {s.get("max_c", "—")}'),
                    ("Mean ± std (°C)", f'{s.get("mean_c", "—")} ± {s.get("std_c", "—")}'),
                    ("Median / IQR (°C)", f'{s.get("median_c", "—")} / {s.get("iqr_c", "—")}'),
                    (
                        "Percentiles P05/P25/P75/P95 (°C)",
                        f'{s.get("p05_c", "—")} / {s.get("p25_c", "—")} / '
                        f'{s.get("p75_c", "—")} / {s.get("p95_c", "—")}',
                    ),
                    ("Skewness / kurtosis", f'{s.get("skewness", "—")} / {s.get("kurtosis", "—")}'),
                    ("Tukey 1.5×IQR outliers", f'{o.get("count", "—")} ({o.get("pct", "—")}%)'),
                    ("Normality test", f'{nm.get("test", "—")} · p = {nm.get("p_value", "—")}'),
                    (
                        "Radial UHI slope",
                        f'{uhi.get("slope_c_per_km", "—")} °C/km (R² = {uhi.get("r2", "—")})',
                    ),
                ]
            )
        )
        advisory = stats.get("advisory")
        if advisory:
            out.append(Spacer(1, 0.2 * cm))
            out.append(_p(advisory, st["Body"]))
        nm_adv = nm.get("advisory")
        if nm_adv:
            out.append(_p(nm_adv, st["Small"]))
        out.append(Spacer(1, 0.3 * cm))
        out.append(_image_from_fig(fig_histogram_normal(stats.get("histogram", {}) or {})))
        if stats.get("hourly_spread"):
            out.append(Spacer(1, 0.2 * cm))
            out.append(_image_from_fig(fig_hourly_boxplot(stats["hourly_spread"])))
        prof = stats.get("radial_profile", {}) or {}
        if prof.get("present"):
            out.append(Spacer(1, 0.2 * cm))
            out.append(_image_from_fig(fig_radial_uhi(prof)))
        out.append(Spacer(1, 0.4 * cm))

    # ----------------------------------------------------- 11 theory vs data
    out.append(_p("11. Theory vs. data", st["H1"]))
    out.append(
        _kv_table(
            [
                ("API tile temperature (°C)", _fmt(tvd.get("measured_tile_c"))),
                ("Predicted skin temperature (°C)", _fmt(tvd.get("predicted_skin_c"))),
                ("Air temperature (°C)", _fmt(tvd.get("air_temperature_c"))),
                ("Tile excess above air (K)", _fmt(tvd.get("tile_excess_above_air_c"))),
                ("Skin excess above air (K)", _fmt(tvd.get("skin_excess_above_air_c"))),
            ]
        )
    )
    verdict = tvd.get("verdict")
    if verdict:
        out.append(Spacer(1, 0.3 * cm))
        out.append(_p(verdict, st["Body"]))
    out.append(Spacer(1, 0.4 * cm))

    # ------------------------------------- 12 elevation lapse correction
    elev = report.get("elevation", {}) or {}
    if elev.get("elevation_m") is not None:
        out.append(_p("12. Elevation & lapse correction", st["H1"]))
        out.append(
            _kv_table(
                [
                    ("District elevation (m a.s.l.)", _fmt(elev.get("elevation_m"))),
                    ("ISA lapse correction 6.5 K/km (°C)", _fmt(elev.get("lapse_correction_c"))),
                    ("Air temperature, raw (°C)", _fmt(elev.get("air_raw_c"))),
                    ("Air temperature, sea-level equivalent (°C)", _fmt(elev.get("air_sea_level_c"))),
                ]
            )
        )
        note = elev.get("note", "")
        if note:
            out.append(Spacer(1, 0.2 * cm))
            out.append(_p(note, st["Small"]))
        out.append(Spacer(1, 0.4 * cm))

    # ------------------------------------------------- 13 street-level landcover
    lc = report.get("landcover", {}) or {}
    if lc.get("present"):
        out.append(_p("13. Street-level landcover evidence", st["H1"]))
        out.append(
            _kv_table(
                [
                    ("Parcel", lc.get("parcel", "—")),
                    ("Sky-view factor — sky % (street)", _fmt(lc.get("svf_sky_pct"), "%")),
                    ("Shade — tree+building % (street)", _fmt(lc.get("shade_pct"), "%")),
                    ("Green — tree+plant % (satellite)", _fmt(lc.get("green_pct"), "%")),
                    ("Impervious — building+ground % (satellite)", _fmt(lc.get("impervious_pct"), "%")),
                ]
            )
        )
        sat = lc.get("satellite", {}) or {}
        sv = lc.get("streetview", {}) or {}
        if sat.get("segments"):
            out.append(Spacer(1, 0.2 * cm))
            out.append(_p(f"Satellite segments: {sat.get('segments')}", st["Small"]))
        if sv.get("segments"):
            out.append(_p(f"Street-view segments: {sv.get('segments')}", st["Small"]))
        note = lc.get("note", "")
        if note:
            out.append(Spacer(1, 0.2 * cm))
            out.append(_p(note, st["Small"]))
        out.append(Spacer(1, 0.4 * cm))
    elif lc:
        out.append(_p("13. Street-level landcover evidence", st["H1"]))
        out.append(_p(lc.get("reason", "no parcel imagery for this district"), st["Small"]))
        out.append(Spacer(1, 0.4 * cm))

    # ---------------------------------------------------- 14 synoptic risk
    syn = report.get("synoptic", {}) or {}
    if syn.get("present"):
        out.append(_p("14. Synoptic risk — heat-wave / heat dome / fire weather", st["H1"]))
        out.append(
            _kv_table(
                [
                    ("Heat-wave-day", str(syn.get("heat_wave_day", "—")) + f" ({syn.get('heat_wave_band', '')})"),
                    ("Longest hot stretch (h ≥ threshold)", _fmt(syn.get("longest_hot_stretch_hours"))),
                    ("Heat-dome / omega-block band", syn.get("dome_band", "—")),
                    ("Fire-weather band (VPD)", syn.get("fire_band", "—")),
                    ("Max VPD (kPa)", _fmt(syn.get("max_vpd_kpa"))),
                    ("Mean VPD (kPa)", _fmt(syn.get("mean_vpd_kpa"))),
                ]
            )
        )
        caveat = syn.get("caveat", "")
        if caveat:
            out.append(Spacer(1, 0.2 * cm))
            out.append(_p(caveat, st["Small"]))
        out.append(Spacer(1, 0.3 * cm))
        out.append(_synoptic_chart(syn))
        out.append(Spacer(1, 0.4 * cm))

    # ------------------------------------------------ 15 provenance & warnings
    out.append(_p("15. Provenance & warnings", st["H1"]))
    out.append(_p(report.get("provenance", ""), st["Small"]))
    warnings = report.get("warnings", []) or []
    if warnings:
        out.append(Spacer(1, 0.3 * cm))
        for w in warnings:
            out.append(_p(f"• {w}", st["Body"]))
    out.append(Spacer(1, 0.8 * cm))
    out.append(
        _p(
            "Generated by calorai — physics-first city heat-budget auditor. "
            "Every number traces to a documented equation (docs/physics-references.md) "
            "and the FortyGuard Temperature API layers.",
            st["Small"],
        )
    )
    return out


class _TOCDoc(SimpleDocTemplate):
    """SimpleDocTemplate that records headings into the table of contents."""

    def afterFlowable(self, flowable: Any) -> None:
        style = getattr(flowable, "style", None)
        if isinstance(flowable, Paragraph) and style is not None:
            text = flowable.getPlainText()
            if style.name == "CaloraiH1":
                self._toc.addEntry(0, text, self.page, None)
            elif style.name == "CaloraiH2":
                self._toc.addEntry(1, text, self.page, None)


def build_pdf_report(report: dict[str, Any], output_path: str | Path | None = None) -> Path:
    """Render the audit report to a PDF; returns the output path."""
    from reportlab.platypus.tableofcontents import TableOfContents

    district = str(report.get("district", "district")).replace(" ", "-")
    date = str(report.get("date", "date"))
    target = Path(output_path) if output_path else OUTPUTS_DIR / f"calorai_{district}_{date}.pdf"
    target.parent.mkdir(parents=True, exist_ok=True)

    st = _styles()
    doc = _TOCDoc(
        str(target),
        pagesize=A4,
        title=f"calorai — Urban Heat Budget Audit · {report.get('district', '')}",
        author="calorai",
        pageCompression=0,  # plain-text content streams: greppable, diff-friendly
    )
    doc._toc = TableOfContents()
    doc._toc.levelStyles = [st["TOCEntry"], st["Small"]]

    story = [_p("Contents", st["H1"]), doc._toc, PageBreak()]
    story.extend(_story(report))
    doc.multiBuild(story)
    return target