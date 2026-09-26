from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from typing import TypeVar

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


@dataclass(frozen=True)
class TextFixture:
    fixture_id: str
    prompt: str
    required_terms: tuple[str, ...]


@dataclass(frozen=True)
class ReceiptFixture:
    fixture_id: str
    invoice_id: str
    total: float
    status: str


@dataclass(frozen=True)
class DocumentFixture:
    fixture_id: str
    project_code: str
    approved_budget: float


@dataclass(frozen=True)
class ToolFixture:
    fixture_id: str
    city: str
    capability: str
    expected_tool: str
    expected_terms: tuple[str, ...]


TEXT_FIXTURES = (
    TextFixture(
        "text-p95",
        "Explain why p95 latency matters for an AI service. Mention 95%, tail latency, "
        "user experience, and capacity planning.",
        ("95", "tail", "user", "capacity"),
    ),
    TextFixture(
        "text-ttft",
        "Explain time to first token for streaming AI. Mention first token, perceived latency, "
        "streaming, and responsiveness.",
        ("first token", "perceived", "stream", "respons"),
    ),
    TextFixture(
        "text-throughput",
        "Explain AI service throughput. Mention requests per second, concurrency, and capacity.",
        ("requests", "second", "concurrency", "capacity"),
    ),
    TextFixture(
        "text-cache",
        "Explain prompt caching. Mention stable prefixes, cached tokens, cost, and latency.",
        ("prefix", "cache", "token", "latency"),
    ),
    TextFixture(
        "text-tools",
        "Explain tool-call latency. Mention selection, execution, model round trips, and total "
        "latency.",
        ("selection", "execution", "round trip", "latency"),
    ),
)

RECEIPT_FIXTURES = (
    ReceiptFixture("receipt-01", "PERF-2026-09", 42.50, "PAID"),
    ReceiptFixture("receipt-02", "LAT-2026-17", 87.25, "APPROVED"),
    ReceiptFixture("receipt-03", "CACHE-2042", 19.95, "SETTLED"),
    ReceiptFixture("receipt-04", "TOOLS-731", 163.40, "PAID"),
    ReceiptFixture("receipt-05", "VISION-88", 56.75, "APPROVED"),
)

DOCUMENT_FIXTURES = (
    DocumentFixture("document-01", "LATENCY-LAB-42", 1250.00),
    DocumentFixture("document-02", "CACHE-STUDY-17", 2875.50),
    DocumentFixture("document-03", "VISION-PERF-09", 940.25),
    DocumentFixture("document-04", "TOOLS-SCALE-31", 4100.00),
    DocumentFixture("document-05", "STREAM-TEST-68", 1675.75),
)

TOOL_FIXTURES = (
    ToolFixture("tool-weather-paris", "Paris", "weather", "lookup_weather", ("21",)),
    ToolFixture(
        "tool-time-berlin",
        "Berlin",
        "local time",
        "get_local_time",
        ("14:30", "2:30 pm", "2:30 p.m."),
    ),
    ToolFixture("tool-weather-tokyo", "Tokyo", "weather", "lookup_weather", ("21",)),
    ToolFixture(
        "tool-time-seattle",
        "Seattle",
        "local time",
        "get_local_time",
        ("14:30", "2:30 pm", "2:30 p.m."),
    ),
    ToolFixture("tool-weather-cairo", "Cairo", "weather", "lookup_weather", ("21",)),
)

FixtureT = TypeVar("FixtureT")


def _fixture(fixtures: tuple[FixtureT, ...], fixture_index: int) -> FixtureT:
    return fixtures[fixture_index % len(fixtures)]


def text_fixture(fixture_index: int = 0) -> TextFixture:
    return _fixture(TEXT_FIXTURES, fixture_index)


def receipt_fixture(fixture_index: int = 0) -> ReceiptFixture:
    return _fixture(RECEIPT_FIXTURES, fixture_index)


def document_fixture(fixture_index: int = 0) -> DocumentFixture:
    return _fixture(DOCUMENT_FIXTURES, fixture_index)


def tool_fixture(fixture_index: int = 0) -> ToolFixture:
    return _fixture(TOOL_FIXTURES, fixture_index)


def receipt_image_data_uri(*, reduced: bool = False, fixture_index: int = 0) -> str:
    fixture = receipt_fixture(fixture_index)
    image = Image.new("RGB", (1200, 800), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=44)
    lines = (
        "PERFORMANCE LAB RECEIPT",
        f"Invoice ID: {fixture.invoice_id}",
        f"Total: ${fixture.total:.2f}",
        f"Status: {fixture.status}",
    )
    for index, line in enumerate(lines):
        draw.text((80, 100 + index * 120), line, fill="black", font=font)
    if reduced:
        image.thumbnail((600, 400), Image.Resampling.LANCZOS)

    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def benchmark_pdf_data_uri(
    *,
    relevant_page_only: bool = False,
    fixture_index: int = 0,
) -> str:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    pages = benchmark_document_pages(fixture_index)
    selected_pages = pages[1:2] if relevant_page_only else pages
    for lines in selected_pages:
        pdf.setFont("Helvetica-Bold", 18)
        pdf.drawString(72, 720, lines[0])
        pdf.setFont("Helvetica", 13)
        for index, line in enumerate(lines[1:]):
            pdf.drawString(72, 680 - index * 32, line)
        pdf.showPage()
    pdf.save()
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:application/pdf;base64,{encoded}"


def benchmark_document_pages(fixture_index: int = 0) -> tuple[str, ...]:
    fixture = document_fixture(fixture_index)
    pages = (
        ("Benchmark cover", "This page contains no target values."),
        (
            "Performance report",
            f"Project code: {fixture.project_code}",
            f"Approved budget: ${fixture.approved_budget:.2f}",
        ),
        ("Appendix", "This page contains background material only."),
    )
    return tuple("\n".join(page) for page in pages)


def benchmark_document_text(
    *,
    relevant_page_only: bool = False,
    fixture_index: int = 0,
) -> str:
    pages = benchmark_document_pages(fixture_index)
    selected_pages = pages[1:2] if relevant_page_only else pages
    return "\n\n".join(selected_pages)
