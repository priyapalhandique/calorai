"""Citizen Heat Mesh — crowdsourced heat reports (mock, no IoT).

POST /api/citizen/report {lat,lon, district, note} -> writes data/citizen/{id}.json (gitignored, committed samples via !data/citizen/*.json)
GET /api/citizen/mesh -> all reports as heat dots for 3D globe.

Mock-safe: no auth, no DB, file-backed. Citizen text 'HEAT' is the resilience hook.
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

CITIZEN_DIR = Path("data/citizen")


def report_heat(lat: float, lon: float, district: str = "phoenix", note: str = "") -> dict[str, Any]:
    CITIZEN_DIR.mkdir(parents=True, exist_ok=True)
    rec = {"id": uuid.uuid4().hex[:8], "lat": float(lat), "lon": float(lon), "district": district, "note": note[:200], "ts": time.time()}
    (CITIZEN_DIR / f"{rec['id']}.json").write_text(json.dumps(rec), encoding="utf-8")
    return rec


def mesh() -> dict[str, Any]:
    CITIZEN_DIR.mkdir(parents=True, exist_ok=True)
    pts: list[dict[str, Any]] = []
    for p in CITIZEN_DIR.glob("*.json"):
        try:
            pts.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            continue
    # also include committed samples
    return {"present": True, "n_reports": len(pts), "reports": pts[-50:], "note": "Citizen text 'HEAT' → report heat here → 3D globe dot. Mock file-backed."}
