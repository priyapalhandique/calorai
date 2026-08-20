"""D7 — planner: turns a natural-language request into a tool plan.

Two layers, both auditable:

1. **Deterministic matcher** — keyword scoring against each tool's
   keyword list; always runs first and always produces a plan, so the
   agent never silently fails offline or without a key.
2. **LLM refinement (best effort)** — a GitHub-Models chat call refines
   tool selection and fills argument values (district, date, hour)
   from the user's phrasing. If the call fails or times out, the
   deterministic plan stands.

The trace (every step: tool, args, ok, summary, ms) is returned with
the answer, so the UI can show exactly which instruments ran.
"""

from __future__ import annotations

import difflib
import json
import re
import time
from typing import Any

from .narrator import GitHubModelsNarrator
from .personal import UserProfile, format_temp
from .tools import AgentContext, _TOOL_KEYWORDS, execute_tool, list_tools

CHAIN_TEMPLATES: dict[str, list[str]] = {
    "plan": ["audit", "forecast", "risk", "respond_mist"],
    "schedule": ["audit", "risk", "respond_mist"],
    "inspect": ["audit", "anomaly", "equity"],
    "compare": ["audit", "equity"],
    "export": ["audit", "export"],
}

#: phrase -> named chain
_CHAIN_TRIGGERS: list[tuple[str, str]] = [
    ("plan", "plan"),
    ("tomorrow", "plan"),
    ("schedule", "schedule"),
    ("prepare", "schedule"),
    ("inspect", "inspect"),
    ("investigat", "inspect"),
    ("compare", "compare"),
    ("benchmark", "compare"),
    ("export", "export"),
    ("download", "export"),
]

_ALIASES: dict[str, str] = {
    "warm": "heat",
    "heat": "heat",
    "temp": "heat",
    "temperature": "heat",
    "cool": "heat",
    "mitigation": "heat",
    "fix": "heat",
    "cover": "heat",
    "reflect": "heat",
    "foresee": "forecast",
    "predict": "forecast",
    "prognosis": "forecast",
    "forecast": "forecast",
    "weird": "anomaly",
    "suspect": "anomaly",
    "anomaly": "anomaly",
    "danger": "risk",
    "risk": "risk",
    "safe": "risk",
    "worker": "risk",
    "health": "risk",
    "mist": "respond_mist",
    "spray": "respond_mist",
    "misting": "respond_mist",
    "respond": "respond_mist",
    "action": "respond_mist",
    "fair": "equity",
    "equity": "equity",
    "gini": "equity",
    "rank": "equity",
    "compare": "equity",
    "labour": "productivity",
    "labor": "productivity",
    "productivity": "productivity",
    "work": "productivity",
    "cost": "economy",
    "money": "economy",
    "economy": "economy",
    "wind": "thermal_wind",
    "breeze": "thermal_wind",
    "circulation": "thermal_wind",
    "ventil": "thermal_wind",
    "airflow": "thermal_wind",
    "downburst": "downburst",
    "outflow": "downburst",
    "rain": "downburst",
    "storm": "downburst",
    "runway": "aviation",
    "airport": "aviation",
    "takeoff": "aviation",
    "flight": "aviation",
    "aircraft": "aviation",
    "airplane": "aviation",
    "download": "export",
    "export": "export",
    "geojson": "export",
    "csv": "export",
    "usage": "usage",
    "credits": "usage",
    "key": "usage",
    "quota": "usage",
    "api": "usage",
    "resume": "usage",
}

_DISTRICT_ALIASES: dict[str, str] = {
    "phoenix": "phoenix",
    "downtown phoenix": "phoenix",
    "san jose": "san-jose",
    "sanjose": "san-jose",
    "diridon": "san-jose",
    "manhattan": "manhattan",
    "nyc": "manhattan",
    "new york": "manhattan",
    "chicago": "chicago",
    "loop": "chicago",
    "austin": "austin",
    "maryvale": "maryvale",
    "west phoenix": "maryvale",
    "vegas": "vegas-strip",
    "las vegas": "vegas-strip",
    "the strip": "vegas-strip",
    "east harlem": "east-harlem",
    "harlem": "east-harlem",
}

_DAY_OFFSETS: dict[str, int] = {
    "today": 0,
    "now": 0,
    "tonight": 0,
    "tomorrow": 1,
    "day after": 2,
}

#: Follow-up pronouns that resolve against the last audited scope.
_FOLLOWUP_RE = re.compile(r"\b(it|its|that|there|here|this city|my city)\b")


def _guess_district(query: str, ctx: AgentContext) -> str | None:
    q = query.lower()
    for alias, canonical in _DISTRICT_ALIASES.items():
        if alias in q:
            return canonical
    # Follow-up resolution (D8): "what about its cost?" -> last district.
    if _FOLLOWUP_RE.search(q) and ctx.last_district:
        return ctx.last_district
    from .data_source import DISTRICTS

    match = difflib.get_close_matches(q.strip(), list(DISTRICTS.keys()), n=1, cutoff=0.6)
    if match:
        return match[0]
    return None


def _guess_hour(query: str, default_hour: int) -> int | None:
    m = re.search(r"\b(\d{1,2})\s*(?:am|pm|:00)?\b", query.lower())
    if not m:
        return None
    num = int(m.group(1))
    text = query.lower()
    if "am" in m.group(0):
        return 6 if num == 6 else num if 5 <= num <= 11 else default_hour
    if "pm" in m.group(0):
        return 14 if num == 2 else min(num + 12, 23) if num <= 11 else default_hour
    if re.search(r"\b(at|noon|midday)\b", text) and num in (12, 14):
        return 14
    return None


def _extract_features(query: str) -> dict[str, Any]:
    args: dict[str, Any] = {}
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", query)
    if m:
        args["date"] = m.group(0)
    return args


def deterministic_plan(query: str, ctx: AgentContext) -> tuple[list[dict[str, Any]], str]:
    """Keyword + chain matching; always returns a concrete plan."""
    q = query.lower()
    steps: list[dict[str, Any]] = []
    mode = "tool"

    # Named chains first (explicit verbs).
    for trigger, chain_name in _CHAIN_TRIGGERS:
        if trigger in q:
            for tool_name in CHAIN_TEMPLATES[chain_name]:
                args: dict[str, Any] = {}
                steps.append({"tool": tool_name, "args": args})
            mode = f"chain:{chain_name}"
            break

    if not steps:
        # Single tool: score every keyword against the query.
        scores: list[tuple[int, str]] = []
        for tool_name, keywords in _TOOL_KEYWORDS.items():
            score = sum(1 for k in keywords if k in q)
            if score:
                scores.append((score, tool_name))
        if not scores:
            steps.append({"tool": "audit", "args": {}})
            mode = "fallback"
        else:
            scores.sort(key=lambda s: -s[0])
            best = scores[0][1]
            if best == "heat":
                best = "audit"
            steps.append({"tool": best, "args": {}})
            mode = f"tool:{best}"

    # Argument enrichment (deterministic).
    district = _guess_district(query, ctx)
    if district:
        steps[0]["args"]["district"] = district
    date = _extract_features(query).get("date")
    if date:
        steps[0]["args"]["date"] = date
    hour = _guess_hour(query, ctx.hour)
    if hour:
        steps[0]["args"]["hour"] = hour
    for step in steps[1:]:
        if "district" in steps[0]["args"]:
            step["args"]["district"] = steps[0]["args"]["district"]

    return steps, mode


def _llm_refine(query: str, ctx: AgentContext, steps: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str | None]:
    """Best-effort LLM refinement of the deterministic plan (never blocks the answer)."""
    tools = list_tools()
    catalog = "\n".join(
        f"- {t['name']}: {t['description']}" for t in tools
    )
    prompt = (
        "You are the planner of a physics-based heat auditor. The user says:\n"
        f"QUERY: {query}\n\n"
        "Available tools:\n" + catalog + "\n\n"
        "Deterministic fallback plan (already decided):\n"
        + json.dumps(steps) + "\n\n"
        'Reply with ONLY a JSON array of {"tool": str, "args": {}} steps. '
        "Choose a coherent sequence (usually 1-4 tools, starting with audit if the "
        "user wants a report). Fill args with district/date/hour if the query names "
        "them. Use the fallback if unsure. No prose, no markdown fences."
    )
    try:
        llm = GitHubModelsNarrator()
        raw = llm.chat(
            prompt,
            system=(
                "You are the planning engine of calorai, a physics-first urban "
                "heat auditor. Reply with ONLY a JSON array of tool steps. "
                "Never invent tools, never add prose."
            ),
            max_tokens=800,
            temperature=0.0,
        )
        text = raw.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:].strip()
        start, end = text.find("["), text.rfind("]")
        if start < 0 or end < start:
            return steps, "no-json"
        parsed = json.loads(text[start : end + 1])
        valid_names = {t["name"] for t in tools}
        plan = [s for s in parsed if isinstance(s, dict) and s.get("tool") in valid_names]
        if not plan:
            return steps, "empty"
        return plan, "ok"
    except Exception:
        return steps, "llm-failed"


def plan_and_run(
    query: str,
    ctx: AgentContext,
    profile: UserProfile | None = None,
) -> dict[str, Any]:
    """Full pipeline: match -> refine -> execute -> trace + answer.

    ``profile`` (D8) personalizes defaults (home district, threshold)
    and the spoken summary (units, work intensity).
    """
    started = time.perf_counter()
    profile = profile or UserProfile()
    run_ctx = ctx
    if profile.home_district or profile.threshold_c is not None:
        run_ctx = AgentContext(
            district=profile.home_district or ctx.district,
            date=ctx.date,
            hour=ctx.hour,
            threshold_c=(
                profile.threshold_c
                if profile.threshold_c is not None
                else ctx.threshold_c
            ),
            source=ctx.source,
        )
        run_ctx.last_district = ctx.last_district
        run_ctx.last_date = ctx.last_date
        run_ctx.last_hour = ctx.last_hour
    steps, mode = deterministic_plan(query, run_ctx)
    refinement = None
    steps, refinement = _llm_refine(query, run_ctx, steps)

    trace: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    for step in steps:
        tr = execute_tool(step["tool"], step.get("args") or {}, run_ctx)
        trace.append(tr.to_dict())
        if tr.ok and tr.result:
            results.append({"tool": tr.name, "result": tr.result, "summary": tr.summary})

    answer = _assemble_answer(query, results, mode, profile)
    tldr = _assemble_tldr(query, results, profile)
    return {
        "query": query,
        "answer": answer,
        "answer_tldr": tldr,
        "mode": mode,
        "refinement": refinement,
        "trace": trace,
        "duration_ms": int((time.perf_counter() - started) * 1000),
    }


def _assemble_answer(
    query: str,
    results: list[dict[str, Any]],
    mode: str,
    profile: UserProfile | None = None,
) -> str:
    """Deterministic markdown answer from tool results (no model required)."""
    lines: list[str] = []
    if not results:
        return "I couldn't run any instruments for that request. Try asking about a district, e.g. \"audit Phoenix at 14:00\"."

    for item in results:
        tool, r = item["tool"], item["result"]
        if tool == "audit":
            lines.append(
                f"**{r['district']} · {r['date']} · {r['snapshot']['hour']}:00**  "
                f"tiles {r['snapshot']['min_c']:.1f}–{r['snapshot']['max_c']:.1f} °C "
                f"(mean {r['snapshot']['mean_c']:.1f}), WBGT {r['exposure']['wbgt_c']:.1f} °C "
                f"({r['exposure']['level']}).\n\n"
                f"Top fix: **{r['interventions'][0]['name']}** "
                f"(−{r['interventions'][0]['delta_t_c']:.1f} °C, "
                f"{r['interventions'][0]['scope']}). "
                f"{r['vulnerability']['score']['band']} overall risk."
            )
        elif tool == "forecast" and r.get("mode") == "district_24h":
            lines.append(
                f"**24-h skin-temperature forecast** (physics-informed surrogate, "
                f"MAE 0.75 °C): peak **{r['peak_skin_c']:.1f} °C at {r['peak_hour']}:00**. "
                "Caveat: the surrogate reproduces the physics solver; skin-vs-canopy layer "
                "semantics still apply."
            )
        elif tool == "forecast":
            lines.append(
                f"Predicted skin temperature: **{r['predicted_skin_c']:.1f} °C** "
                f"for the given conditions."
            )
        elif tool == "risk":
            ex = r["exposure"]
            ex_text = (
                f"threshold exceeded {ex.get('exceedance_hours', 0)} h/cell"
                if ex.get("exceedance_available") else
                "exceedance layer unavailable (live plan limit)"
            )
            lines.append(
                f"Heat risk: WBGT **{ex['wbgt_c']:.1f} °C** "
                f"({ex['level']}), {ex_text}. "
                f"Downburst watch: **{r['downburst'].get('peak_risk', 'low')}** "
                f"at {r['downburst'].get('peak_hour', '?')}:00."
            )
        elif tool == "respond_mist":
            m = r["misting"]
            lines.append(
                f"Misting: **{m['level']}** — {m['headline']}\n\n"
                f"Placement: {m['placement']} side; water {m['water_m3_per_hour']} m³/h, "
                f"energy {m['energy_kwh_per_hour']} kWh/h. "
                f"Heat-response band: **{r['heat_response']['band']}** — "
                + "; ".join(a["action"] for a in r["heat_response"]["actions"][:2])
                + "."
            )
        elif tool == "anomaly":
            lines.append(
                f"Anomalies: **{r['n_flagged']}/{r['n_tiles']}** tiles flagged "
                f"({r['flagged_pct']:.0f}%). {r.get('advisory', '')}"
            )
        elif tool == "equity":
            lines.append(
                f"Equity: Gini **{r['equity']['gini']:.2f}**, quintile gap "
                f"**{r['equity']['quintile_gap_c']:.1f} K**, heat burden "
                f"{r['equity'].get('heat_burden', 'n/a')}."
            )
        elif tool == "productivity":
            lines.append(
                f"Productivity: moderate work capacity **{100 - r['moderate']['loss_pct']:.0f}%** "
                f"at WBGT {r['wbgt_c']:.1f} °C."
            )
        elif tool == "economy":
            lines.append(
                f"Cost of heat: **${r['total_usd_per_year']:,.0f}/yr** "
                f"(cooling ${r['cooling_usd_per_year']:,.0f} + productivity "
                f"${r['productivity_usd_per_year']:,.0f})."
            )
        elif tool == "thermal_wind":
            lines.append(
                f"Circulation: inflow from the **{r.get('inflow_direction', 'uniform')}**; "
                f"Δp {r.get('pressure_deficit_hpa', 0)} hPa, "
                f"{r.get('ventilation_corridors', 0)} corridor(s). "
                f"Speed scale {r.get('inflow_speed_scale_m_s', 0)} m/s."
            )
        elif tool == "downburst":
            lines.append(
                f"Downburst diagnostic: peak **{r.get('peak_risk', 'low')}** "
                f"at {r.get('peak_hour', '?')}:00; {r.get('watch_text', '')}"
            )
        elif tool == "aviation":
            lines.append(
                f"Runway heat: DA **{r['density_altitude_m']:.0f} m** "
                f"({r['density_altitude_ft']:.0f} ft), takeoff-distance factor "
                f"**{r['takeoff_distance_factor']:.2f}**, tire/tarmac risk "
                f"**{r['surface_risk']}**. {r['advisory']}"
            )
        elif tool == "export":
            lines.append(
                f"Interop package ready: **{r['filename']}** ({r['bytes']} bytes) — "
                "tiles.geojson + audit.csv + interventions.csv."
            )
        elif tool == "usage":
            lines.append(f"Data mode: **{r['mode']}** ({r.get('source', '')}).")
        else:
            lines.append(item["summary"])

    personal = _personalize(results, profile)
    if personal:
        lines.append(personal)
    unit_note = _unit_note(results, profile)
    if unit_note:
        lines.append(unit_note)
    lines.append(f"*Mode: {mode}; {len(results)} instrument(s) ran; every number traces to the physics layer.*")
    return "\n\n".join(lines)


def _personalize(
    results: list[dict[str, Any]], profile: UserProfile | None
) -> str | None:
    """Work-intensity personalization for planning/risk answers (D8)."""
    if profile is None:
        return None
    for item in results:
        r = item["result"]
        if item["tool"] in ("audit", "risk"):
            prod = (r.get("analysis") or {}).get("productivity") or {}
            block = prod.get(profile.intensity) or {}
            loss = block.get("loss_pct")
            if loss is not None:
                usd = block.get("usd_per_year")
                usd_text = f" (≈ ${usd:,.0f} USD/yr)" if usd is not None else ""
                return (
                    f"For your **{profile.intensity}-work** profile, the heat burden "
                    f"cuts work capacity by **{loss}%**{usd_text} at this hour."
                )
    return None


def _unit_note(
    results: list[dict[str, Any]], profile: UserProfile | None
) -> str | None:
    """Honest unit note: the markdown body stays °C; the note shows the
    profile's conversion once, and the spoken summary uses °F."""
    if profile is None or profile.units != "f":
        return None
    for item in results:
        r = item["result"]
        if item["tool"] == "audit":
            c = r["snapshot"]["max_c"]
        elif item["tool"] == "forecast" and r.get("mode") == "district_24h":
            c = r["peak_skin_c"]
        elif item["tool"] == "forecast":
            c = r["predicted_skin_c"]
        elif item["tool"] == "risk":
            c = r["exposure"]["wbgt_c"]
        else:
            continue
        return f"Unit preference: °F active — {c:.1f} °C ≈ {c * 9.0 / 5.0 + 32.0:.1f} °F."
    return None


def _assemble_tldr(
    query: str,
    results: list[dict[str, Any]],
    profile: UserProfile | None,
) -> str:
    """One spoken-ready sentence; °F when the profile asks for it (D8)."""
    if not results:
        return "I could not run any instruments for that request."
    u = profile.units if profile else "c"
    item = results[0]
    r = item["result"]
    tool = item["tool"]
    if tool == "audit":
        return (
            f"{r['district']} at {r['snapshot']['hour']}:00 — tiles peak at "
            f"{format_temp(r['snapshot']['max_c'], u)}, WBGT "
            f"{format_temp(r['exposure']['wbgt_c'], u)}, "
            f"{r['vulnerability']['score']['band']} overall risk."
        )
    if tool == "forecast" and r.get("mode") == "district_24h":
        return f"Forecast peak {format_temp(r['peak_skin_c'], u)} at {r['peak_hour']}:00."
    if tool == "forecast":
        return f"Predicted skin temperature {format_temp(r['predicted_skin_c'], u)}."
    if tool == "risk":
        return (
            f"Heat risk for {r['district']}: WBGT {format_temp(r['exposure']['wbgt_c'], u)}, "
            f"{r['exposure']['level']}."
        )
    if tool == "respond_mist":
        m = r.get("misting") or {}
        if m:
            return (
                f"Misting recommended: {m.get('placement', '')} side, "
                f"{m.get('water_m3_per_hour', '')} cubic meters per hour."
            )
    if tool == "economy":
        return (
            f"District cost of heat: about ${r.get('total_usd_per_year', 0):,.0f} "
            f"US dollars per year."
        )
    return str(item.get("summary") or "Done.")