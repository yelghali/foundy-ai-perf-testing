import pytest

from ai_perf.models import TokenUsage
from ai_perf.results import (
    bootstrap_median_ci,
    bootstrap_median_comparison,
    percentile,
    summarize_total_latency,
)


def test_percentile_uses_nearest_rank() -> None:
    values = list(range(1, 21))

    assert percentile(values, 0.95) == 19
    assert percentile(values, 0.99) == 20


def test_summary_reports_latency_distribution() -> None:
    observations = [{"total_ms": value} for value in (10, 20, 30, 40)]

    assert summarize_total_latency(observations) == {
        "count": 4,
        "mean_ms": 25.0,
        "p50_ms": 25.0,
        "p95_ms": 40.0,
        "p99_ms": 40.0,
    }


def test_empty_summary_is_rejected() -> None:
    with pytest.raises(ValueError, match="No observations"):
        summarize_total_latency([])


def test_token_usage_adds_optional_values() -> None:
    combined = TokenUsage(input_tokens=10, cached_tokens=5) + TokenUsage(
        input_tokens=20,
        output_tokens=4,
    )

    assert combined == TokenUsage(input_tokens=30, output_tokens=4, cached_tokens=5)


def test_bootstrap_median_is_deterministic() -> None:
    values = [10.0, 20.0, 30.0, 40.0, 50.0]

    first = bootstrap_median_ci(values, resamples=200, seed=7)
    second = bootstrap_median_ci(values, resamples=200, seed=7)

    assert first == second
    assert first[0] <= 30 <= first[1]


def test_paired_bootstrap_preserves_round_effect() -> None:
    control = [100.0, 200.0, 300.0, 400.0]
    treatment = [70.0, 170.0, 270.0, 370.0]

    intervals = bootstrap_median_comparison(
        treatment,
        control,
        paired=True,
        resamples=200,
        seed=11,
    )

    assert intervals["delta_ms"] == (-30.0, -30.0)
    assert intervals["change_percent"][1] < 0
