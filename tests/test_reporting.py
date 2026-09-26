from pathlib import Path

from ai_perf.reporting import build_summary, write_html_report


def test_report_summary_excludes_failed_latency(tmp_path: Path) -> None:
    observations = [
        {
            "scenario": "text_chat",
            "variant": "baseline",
            "model": "test",
            "success": True,
            "total_ms": 100,
            "first_token_ms": 40,
            "output_tokens_per_second": 20,
            "quality_score": 1.0,
            "usage": {
                "input_tokens": 80,
                "output_tokens": 20,
                "cached_tokens": 0,
                "reasoning_tokens": 4,
            },
            "service_tier_requested": "priority",
            "service_tier_actual": "default",
            "metadata": {
                "concurrency": 5,
                "batch_elapsed_ms": 2000,
                "throughput_requests_per_second": 10,
            },
        },
        {
            "scenario": "text_chat",
            "variant": "baseline",
            "model": "test",
            "success": False,
            "total_ms": 1,
            "quality_score": None,
            "usage": {},
            "error_type": "RuntimeError",
            "error_message": "failed",
        },
    ]

    summary = build_summary(observations)
    report = tmp_path / "report.html"
    write_html_report(report, summary)

    assert summary[0]["p50_ms"] == 100
    assert summary[0]["success_rate"] == 0.5
    assert summary[0]["average_first_token_ms"] == 40
    assert summary[0]["average_input_tokens"] == 80
    assert summary[0]["requested_service_tiers"] == {"priority": 1}
    assert summary[0]["actual_service_tiers"] == {"default": 1}
    assert summary[0]["concurrency_levels"] == {"5": 1}
    assert summary[0]["batch_elapsed_ms"] == 2000
    assert summary[0]["throughput_requests_per_second"] == 10
    assert "text_chat" in report.read_text(encoding="utf-8")


def test_report_builds_paired_baseline_comparison() -> None:
    observations = []
    for round_index, baseline_ms in enumerate(
        (100, 110, 120, 130, 140, 150, 160, 170, 180, 190)
    ):
        shared = {
            "scenario": "text_chat",
            "model": "test",
            "success": True,
            "quality_passed": True,
            "quality_score": 1.0,
            "usage": {},
            "metadata": {
                "schedule": "interleaved",
                "round": round_index,
                "fixture_id": f"fixture-{round_index % 3}",
            },
        }
        observations.append({**shared, "variant": "baseline", "total_ms": baseline_ms})
        observations.append(
            {
                **shared,
                "variant": "concise-output",
                "total_ms": baseline_ms - 30,
            }
        )

    summary = build_summary(observations)
    concise = next(row for row in summary if row["variant"] == "concise-output")

    assert concise["correct_completion_rate"] == 1.0
    assert concise["fixture_count"] == 3
    assert concise["control_variant"] == "baseline"
    assert concise["comparison_method"] == "paired-by-randomized-round"
    assert concise["p50_delta_ms"] == -30
    assert concise["p50_delta_ci95_ms"] == [-30.0, -30.0]
    assert concise["faster_with_95pct_confidence"] is True


def test_report_does_not_infer_from_a_preflight_sample() -> None:
    shared = {
        "scenario": "text_chat",
        "model": "test",
        "success": True,
        "quality_passed": True,
        "quality_score": 1.0,
        "usage": {},
        "metadata": {"schedule": "interleaved", "round": 0},
    }
    observations = [
        {**shared, "variant": "baseline", "total_ms": 200},
        {**shared, "variant": "concise-output", "total_ms": 100},
    ]

    summary = build_summary(observations)
    concise = next(row for row in summary if row["variant"] == "concise-output")

    assert concise["p50_ci95_ms"] is None
    assert "p50_delta_ci95_ms" not in concise
    assert "faster_with_95pct_confidence" not in concise


def test_bundle_report_compares_priority_directly_with_worst() -> None:
    observations = []
    for round_index in range(10):
        shared = {
            "scenario": "text_chat",
            "model": "priority-supported",
            "success": True,
            "quality_passed": True,
            "quality_score": 1.0,
            "usage": {},
            "metadata": {
                "schedule": "interleaved",
                "round": round_index,
            },
        }
        observations.extend(
            [
                {
                    **shared,
                    "variant": "bundle-worst-standard",
                    "total_ms": 200,
                },
                {
                    **shared,
                    "variant": "bundle-best-standard",
                    "total_ms": 150,
                },
                {
                    **shared,
                    "variant": "bundle-best-priority",
                    "total_ms": 100,
                },
            ]
        )

    summary = build_summary(observations)
    priority = next(
        row for row in summary if row["variant"] == "bundle-best-priority"
    )

    assert priority["p50_change_percent"] == -100 / 3
    assert priority["overall_control_variant"] == "bundle-worst-standard"
    assert priority["overall_p50_change_percent"] == -50
    assert priority["overall_p50_change_ci95_percent"] == [-50.0, -50.0]
    assert priority["overall_faster_with_95pct_confidence"] is True
