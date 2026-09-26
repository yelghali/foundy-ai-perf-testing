from ai_perf.quality import score_fields, score_term_groups, score_terms


def test_term_score_reports_partial_quality() -> None:
    result = score_terms("95 percent tail latency", ("95", "tail", "user", "capacity"))

    assert result.score == 0.5
    assert not result.passed


def test_term_groups_accept_equivalent_time_formats() -> None:
    result = score_term_groups(
        "The local time is 2:30 PM and the temperature is 21 C.",
        {
            "time": ("14:30", "2:30 pm", "2:30 p.m."),
            "temperature": ("21",),
        },
    )

    assert result.score == 1.0
    assert result.passed


def test_field_score_requires_exact_values() -> None:
    result = score_fields(
        '{"invoice_id":"PERF-2026-09","total":42.5,"status":"PAID"}',
        {"invoice_id": "PERF-2026-09", "total": 42.5, "status": "PAID"},
    )

    assert result.score == 1.0
    assert result.passed


def test_invalid_json_fails_quality() -> None:
    result = score_fields("not json", {"value": 1})

    assert result.score == 0.0
    assert not result.passed
    assert "parse_error" in result.details
