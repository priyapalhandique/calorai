"""PDF report tests — build the judge-ready artifact from a mock audit
and verify it is a real, multi-page, chart-bearing PDF.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from calorai.agent import AuditAgent, AuditRequest
from calorai.report import build_pdf_report


@pytest.fixture(scope="module")
def pdf_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    report = AuditAgent(
        AuditRequest("phoenix", "2026-07-15", hour=14, data_source="mock")
    ).run(narrate=False)
    return build_pdf_report(report, tmp_path_factory.mktemp("pdf") / "audit.pdf")


def test_pdf_file_exists_and_is_not_trivial(pdf_path: Path) -> None:
    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 20_000  # charts push it well past text-only


def test_pdf_has_pdf_header(pdf_path: Path) -> None:
    head = pdf_path.read_bytes()[:5]
    assert head == b"%PDF-"


def test_pdf_is_multi_page(pdf_path: Path) -> None:
    raw = pdf_path.read_bytes()
    assert raw.count(b"/Type /Page") >= 3


def test_pdf_contains_section_headings(pdf_path: Path) -> None:
    raw = pdf_path.read_bytes().decode("latin-1", errors="ignore")
    for expected in (
        "District snapshot",
        "Energy attribution",
        "Street canyon",
        "Thermal inertia",
        "Heat exposure",
        "Interventions",
        "Vulnerability",
        "Facade-orientation",
        "Theory vs. data",
        "Provenance",
    ):
        assert expected in raw, f"missing section: {expected}"


def test_pdf_embeds_chart_images(pdf_path: Path) -> None:
    raw = pdf_path.read_bytes()
    # matplotlib figures embedded as image XObjects.
    assert b"/XObject" in raw and b"/Image" in raw