import base64

from ai_perf.fixtures import (
    benchmark_document_pages,
    benchmark_document_text,
    benchmark_pdf_data_uri,
    document_fixture,
    receipt_fixture,
    receipt_image_data_uri,
    text_fixture,
    tool_fixture,
)


def _decode_data_uri(value: str) -> bytes:
    _, encoded = value.split(",", maxsplit=1)
    return base64.b64decode(encoded)


def test_receipt_fixture_is_a_png() -> None:
    assert _decode_data_uri(receipt_image_data_uri()).startswith(b"\x89PNG\r\n\x1a\n")


def test_file_fixture_is_a_pdf() -> None:
    assert _decode_data_uri(benchmark_pdf_data_uri()).startswith(b"%PDF")


def test_extracted_document_fixture_matches_pdf_content() -> None:
    pages = benchmark_document_pages()

    assert len(pages) == 3
    assert "LATENCY-LAB-42" in benchmark_document_text()
    assert benchmark_document_text(relevant_page_only=True) == pages[1]


def test_fixture_sets_rotate_across_five_balanced_inputs() -> None:
    assert len({text_fixture(index).fixture_id for index in range(5)}) == 5
    assert len({receipt_fixture(index).invoice_id for index in range(5)}) == 5
    assert len({document_fixture(index).project_code for index in range(5)}) == 5
    assert {tool_fixture(index).expected_tool for index in range(5)} == {
        "lookup_weather",
        "get_local_time",
    }


def test_generated_fixtures_include_selected_values() -> None:
    receipt = receipt_fixture(3)
    document = document_fixture(3)

    assert _decode_data_uri(receipt_image_data_uri(fixture_index=3)).startswith(
        b"\x89PNG\r\n\x1a\n"
    )
    assert receipt.invoice_id == "TOOLS-731"
    assert document.project_code in benchmark_document_text(fixture_index=3)
