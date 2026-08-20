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
    audit.add_argument("--pdf", action="store_true", help="also render a PDF report to outputs/")
    audit.add_argument(
        "--export-out", metavar="DIR", default=None,
        help="also write the Forma-friendly interop package (GeoJSON + CSVs) to DIR",
    )

    sub.add_parser("serve", help="run the FastAPI web app on :8000")

    ask = sub.add_parser(
        "ask",
        help="ask the agent a natural-language question (D7)",
    )
    ask.add_argument("query", help="natural-language request, e.g. \"plan tomorrow for Maryvale\"")
    ask.add_argument("--district", default="phoenix", help="default district if the query names none")
    ask.add_argument("--date", default="2026-08-18", help="default date if the query names none")
    ask.add_argument("--hour", type=int, default=14, help="default audit hour")
    ask.add_argument("--mock", action="store_true", help="force offline mock data")
    ask.add_argument("--json", action="store_true", help="emit the full plan+trace payload")

    train = sub.add_parser(
        "train-forecast",
        help="train the physics-informed forecast surrogate (ML, D6)",
    )
    train.add_argument("--rows", type=int, default=100_000, help="synthetic rows to train on")
    train.add_argument("--out", default="data/models/forecast_v1.joblib", help="artifact path")

    args = parser.parse_args(argv)

    if args.command == "serve":
        import uvicorn

        uvicorn.run("calorai.main:app", host="127.0.0.1", port=8000)
        return 0

    if args.command == "ask":
        from .planner import plan_and_run
        from .tools import AgentContext

        out = plan_and_run(
            args.query,
            AgentContext(
                district=args.district,
                date=args.date,
                hour=args.hour,
                source="mock" if args.mock else None,
            ),
        )
        if args.json:
            print(json.dumps(out, indent=2, default=str))
        else:
            print(out["answer"])
            print(
                f"\n[mode {out['mode']} · refinement {out['refinement']} · "
                f"{len(out['trace'])} tool(s) · {out['duration_ms']} ms]"
            )
        return 0

    if args.command == "train-forecast":
        from .ml.forecast import train_forecast

        train_forecast(n_rows=args.rows, out_path=args.out)
        return 0

    from .agent import AuditAgent, AuditRequest

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
    if args.pdf:
        from .report import build_pdf_report

        path = build_pdf_report(report)
        print(f"PDF report written to {path}")
    if args.export_out:
        from .interop import export_audit

        snapshot = AuditAgent(request).fetch_snapshot()
        for path in export_audit(report, snapshot, args.threshold, args.export_out):
            print(f"interop export written to {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())