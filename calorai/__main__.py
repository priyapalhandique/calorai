"""CLI — run heat-budget audits from the terminal.

Examples
--------
    python -m calorai audit phoenix --date 2026-08-18 --hour 14
    python -m calorai audit san-jose --mock
    python -m calorai serve
"""

from __future__ import annotations

import argparse
import json
import sys


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(prog="calorai")
    sub = parser.add_subparsers(dest="command", required=True)

    audit = sub.add_parser("audit", help="run a district heat-budget audit")
    audit.add_argument("district", help="district key, e.g. phoenix")
    audit.add_argument("--date", default="2024-07-15", help="YYYY-MM-DD (data-proven example date)")
    audit.add_argument("--hour", type=int, default=14, help="audit hour 0-23")
    audit.add_argument("--threshold", type=float, default=30.0, help="exceedance threshold °C")
    audit.add_argument("--no-exceedance", action="store_true")
    audit.add_argument("--json", action="store_true", help="emit structured report, no narration")
    audit.add_argument("--mock", action="store_true", help="force offline mock data")
    audit.add_argument("--narrator", default="auto", choices=("auto", "template", "github-models"))

    sub.add_parser("serve", help="run the FastAPI web app on :8000")

    args = parser.parse_args(argv)

    from .agent import AuditAgent, AuditRequest

    if args.command == "serve":
        import uvicorn

        uvicorn.run("calorai.main:app", host="127.0.0.1", port=8000)
        return 0

    request = AuditRequest(
        district=args.district,
        date=args.date,
        hour=args.hour,
        threshold_c=args.threshold,
        with_exceedance=not args.no_exceedance,
        data_source="mock" if args.mock else None,
        narrator_kind=args.narrator,
    )
    report = AuditAgent(request).run(narrate=not args.json)
    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print(report["narrative"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())