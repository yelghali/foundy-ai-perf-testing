from __future__ import annotations

import html
import json
import zlib
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median
from typing import Any

from ai_perf.results import (
    bootstrap_median_ci,
    bootstrap_median_comparison,
    percentile,
)

SCENARIO_BASELINES = {
    "text_chat": "baseline",
    "image_understanding": "baseline",
    "file_processing": "baseline",
    "tool_calling": "native-baseline",
}

SPECIAL_CONTROLS: dict[str, str | None] = {
    "cache-cold": None,
    "cache-warm": "cache-cold",
    "mcp-cold": "mcp-warm",
    "sequential-pages": None,
    "parallel-pages": "sequential-pages",
    "sequential-tools": None,
    "parallel-tools": "sequential-tools",
    "mcp-remote-50": None,
    "foundry-toolbox-search-50": "mcp-remote-50",
    "reordered-definitions": "cache-warm",
    "bundle-worst-standard": None,
    "bundle-best-standard": "bundle-worst-standard",
    "bundle-best-priority": "bundle-best-standard",
}
MIN_BOOTSTRAP_SAMPLE_SIZE = 10


def _is_correct(item: dict[str, Any]) -> bool:
    return bool(item.get("success", True)) and item.get("quality_passed") is not False


def _control_variant(scenario: str, variant: str) -> str | None:
    baseline = SCENARIO_BASELINES[scenario]
    if variant == baseline:
        return None
    return SPECIAL_CONTROLS.get(variant, baseline)


def _comparison_seed(scenario: str, variant: str, model: str) -> int:
    identifier = f"{scenario}/{variant}/{model}".encode()
    return 20260904 + zlib.crc32(identifier)


def _round_latencies(group: list[dict[str, Any]]) -> dict[int, float]:
    return {
        int(item["metadata"]["round"]): float(item["total_ms"])
        for item in group
        if _is_correct(item)
        and isinstance(item.get("metadata"), dict)
        and item["metadata"].get("schedule") == "interleaved"
        and item["metadata"].get("round") is not None
    }


def _comparison_metrics(
    scenario: str,
    variant: str,
    model: str,
    treatment_group: list[dict[str, Any]],
    control_group: list[dict[str, Any]],
) -> dict[str, Any]:
    treatment_latencies = [float(item["total_ms"]) for item in treatment_group]
    control_latencies = [float(item["total_ms"]) for item in control_group]
    if (
        len(treatment_latencies) < MIN_BOOTSTRAP_SAMPLE_SIZE
        or len(control_latencies) < MIN_BOOTSTRAP_SAMPLE_SIZE
    ):
        return {}

    treatment_rounds = _round_latencies(treatment_group)
    control_rounds = _round_latencies(control_group)
    shared_rounds = sorted(treatment_rounds.keys() & control_rounds.keys())
    paired = len(shared_rounds) >= MIN_BOOTSTRAP_SAMPLE_SIZE
    if paired:
        comparison_treatment = [treatment_rounds[index] for index in shared_rounds]
        comparison_control = [control_rounds[index] for index in shared_rounds]
    else:
        comparison_treatment = treatment_latencies
        comparison_control = control_latencies

    intervals = bootstrap_median_comparison(
        comparison_treatment,
        comparison_control,
        paired=paired,
        seed=_comparison_seed(scenario, variant, model),
    )
    treatment_p50 = median(treatment_latencies)
    control_p50 = median(control_latencies)
    delta = treatment_p50 - control_p50
    delta_interval = intervals["delta_ms"]
    return {
        "comparison_method": (
            "paired-by-randomized-round" if paired else "independent-bootstrap"
        ),
        "comparison_count": len(comparison_treatment),
        "p50_delta_ms": delta,
        "p50_delta_ci95_ms": list(delta_interval),
        "p50_change_percent": 100 * delta / control_p50,
        "p50_change_ci95_percent": list(intervals["change_percent"]),
        "faster_with_95pct_confidence": delta_interval[1] < 0,
        "slower_with_95pct_confidence": delta_interval[0] > 0,
    }


def build_summary(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for observation in observations:
        grouped[
            (
                str(observation["scenario"]),
                str(observation["variant"]),
                str(observation["model"]),
            )
        ].append(observation)

    summary: list[dict[str, Any]] = []
    correct_groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for (scenario, variant, model), group in sorted(grouped.items()):
        successful = [item for item in group if item.get("success", True)]
        correct = [item for item in successful if _is_correct(item)]
        correct_groups[(scenario, variant, model)] = correct
        latencies = [float(item["total_ms"]) for item in correct]
        quality_scores = [
            float(item["quality_score"])
            for item in successful
            if item.get("quality_score") is not None
        ]
        first_token_latencies = [
            float(item["first_token_ms"])
            for item in successful
            if item.get("first_token_ms") is not None
        ]
        output_rates = [
            float(item["output_tokens_per_second"])
            for item in successful
            if item.get("output_tokens_per_second") is not None
        ]
        cached = [
            int(item["usage"].get("cached_tokens") or 0)
            for item in successful
            if isinstance(item.get("usage"), dict)
        ]
        input_tokens = [
            int(item["usage"]["input_tokens"])
            for item in successful
            if isinstance(item.get("usage"), dict)
            and item["usage"].get("input_tokens") is not None
        ]
        output_tokens = [
            int(item["usage"]["output_tokens"])
            for item in successful
            if isinstance(item.get("usage"), dict)
            and item["usage"].get("output_tokens") is not None
        ]
        reasoning_tokens = [
            int(item["usage"]["reasoning_tokens"])
            for item in successful
            if isinstance(item.get("usage"), dict)
            and item["usage"].get("reasoning_tokens") is not None
        ]
        timing_names = {name for item in successful for name in item.get("timings_ms", {})}
        average_timings = {
            name: mean(
                float(item["timings_ms"][name])
                for item in successful
                if name in item.get("timings_ms", {})
            )
            for name in sorted(timing_names)
        }
        actual_tiers = Counter(
            str(item["service_tier_actual"])
            for item in successful
            if item.get("service_tier_actual") is not None
        )
        requested_tiers = Counter(
            str(item["service_tier_requested"])
            for item in successful
            if item.get("service_tier_requested") is not None
        )
        concurrency_levels = Counter(
            str(item["metadata"]["concurrency"])
            for item in group
            if isinstance(item.get("metadata"), dict)
            and item["metadata"].get("concurrency") is not None
        )
        batch_elapsed = [
            float(item["metadata"]["batch_elapsed_ms"])
            for item in group
            if isinstance(item.get("metadata"), dict)
            and item["metadata"].get("batch_elapsed_ms") is not None
        ]
        throughput = [
            float(item["metadata"]["throughput_requests_per_second"])
            for item in group
            if isinstance(item.get("metadata"), dict)
            and item["metadata"].get("throughput_requests_per_second") is not None
        ]
        schedules = Counter(
            str(item["metadata"]["schedule"])
            for item in group
            if isinstance(item.get("metadata"), dict)
            and item["metadata"].get("schedule") is not None
        )
        fixture_ids = {
            str(item["metadata"]["fixture_id"])
            for item in group
            if isinstance(item.get("metadata"), dict)
            and item["metadata"].get("fixture_id") is not None
        }
        requested_tier_matches = [
            item.get("service_tier_actual") == item.get("service_tier_requested")
            for item in successful
            if item.get("service_tier_requested") is not None
        ]
        seed = _comparison_seed(scenario, variant, model)
        summary.append(
            {
                "scenario": scenario,
                "variant": variant,
                "model": model,
                "count": len(group),
                "success_rate": len(successful) / len(group),
                "correct_count": len(correct),
                "correct_completion_rate": len(correct) / len(group),
                "quality_score": mean(quality_scores) if quality_scores else None,
                "p50_ms": median(latencies) if latencies else None,
                "p95_ms": percentile(latencies, 0.95) if latencies else None,
                "p99_ms": percentile(latencies, 0.99) if latencies else None,
                "p50_ci95_ms": (
                    list(bootstrap_median_ci(latencies, seed=seed))
                    if len(latencies) >= MIN_BOOTSTRAP_SAMPLE_SIZE
                    else None
                ),
                "mean_ms": mean(latencies) if latencies else None,
                "average_first_token_ms": (
                    mean(first_token_latencies) if first_token_latencies else None
                ),
                "average_output_tokens_per_second": (
                    mean(output_rates) if output_rates else None
                ),
                "average_input_tokens": mean(input_tokens) if input_tokens else None,
                "average_output_tokens": mean(output_tokens) if output_tokens else None,
                "average_reasoning_tokens": (
                    mean(reasoning_tokens) if reasoning_tokens else None
                ),
                "cache_hit_rate": (
                    sum(value > 0 for value in cached) / len(cached) if cached else None
                ),
                "average_cached_tokens": mean(cached) if cached else None,
                "average_timings_ms": average_timings,
                "requested_service_tiers": dict(requested_tiers),
                "actual_service_tiers": dict(actual_tiers),
                "requested_tier_match_rate": (
                    mean(requested_tier_matches) if requested_tier_matches else None
                ),
                "concurrency_levels": dict(concurrency_levels),
                "schedules": dict(schedules),
                "fixture_count": len(fixture_ids),
                "batch_elapsed_ms": mean(batch_elapsed) if batch_elapsed else None,
                "throughput_requests_per_second": (
                    mean(throughput) if throughput else None
                ),
                "errors": [
                    {
                        "type": item.get("error_type"),
                        "message": item.get("error_message"),
                    }
                    for item in group
                    if not item.get("success", True)
                ],
                "quality_failures": sum(
                    item.get("success", True) and item.get("quality_passed") is False
                    for item in group
                ),
            }
        )

    rows_by_case = {
        (str(row["scenario"]), str(row["variant"]), str(row["model"])): row
        for row in summary
    }
    for key, row in rows_by_case.items():
        scenario, variant, model = key
        control_variant = _control_variant(scenario, variant)
        row["control_variant"] = control_variant
        if control_variant is None:
            continue

        candidates = [
            candidate_key
            for candidate_key in correct_groups
            if candidate_key[0] == scenario and candidate_key[1] == control_variant
        ]
        if not candidates:
            continue
        same_model = [candidate for candidate in candidates if candidate[2] == model]
        control_key = same_model[0] if same_model else candidates[0]
        treatment_group = correct_groups[key]
        control_group = correct_groups[control_key]
        comparison = _comparison_metrics(
            scenario,
            variant,
            model,
            treatment_group,
            control_group,
        )
        if comparison:
            row.update({"control_model": control_key[2], **comparison})

        if variant != "bundle-best-priority":
            continue
        overall_key = (scenario, "bundle-worst-standard", model)
        if overall_key not in correct_groups:
            continue
        overall = _comparison_metrics(
            scenario,
            f"{variant}-vs-worst",
            model,
            treatment_group,
            correct_groups[overall_key],
        )
        row["overall_control_variant"] = "bundle-worst-standard"
        if overall:
            row.update({f"overall_{name}": value for name, value in overall.items()})
    return summary


def write_summary_json(path: Path, summary: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2), encoding="utf-8")


def write_html_report(path: Path, summary: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    valid_p50 = [float(row["p50_ms"]) for row in summary if row["p50_ms"] is not None]
    max_p50 = max(valid_p50, default=1.0)
    rows: list[str] = []
    bars: list[str] = []
    for index, row in enumerate(summary):
        p50 = row["p50_ms"]
        p95 = row["p95_ms"]
        p99 = row["p99_ms"]
        quality = row["quality_score"]
        errors = row["errors"]
        quality_cell = f"<td>{quality:.0%}</td>" if quality is not None else "<td>-</td>"
        p50_cell = f"<td>{p50:.1f}</td>" if p50 is not None else "<td>-</td>"
        p95_cell = f"<td>{p95:.1f}</td>" if p95 is not None else "<td>-</td>"
        p99_cell = f"<td>{p99:.1f}</td>" if p99 is not None else "<td>-</td>"
        change = row.get("p50_change_percent")
        change_interval = row.get("p50_change_ci95_percent")
        if change is not None and change_interval is not None:
            change_cell = (
                f"<td>{change:+.1f}% "
                f"[{change_interval[0]:+.1f}%, {change_interval[1]:+.1f}%]</td>"
            )
        else:
            change_cell = "<td>-</td>"
        overall_change = row.get("overall_p50_change_percent")
        overall_interval = row.get("overall_p50_change_ci95_percent")
        if overall_change is not None and overall_interval is not None:
            overall_change_cell = (
                f"<td>{overall_change:+.1f}% "
                f"[{overall_interval[0]:+.1f}%, {overall_interval[1]:+.1f}%]</td>"
            )
        else:
            overall_change_cell = "<td>-</td>"
        rows.append(
            "<tr>"
            f"<td>{html.escape(row['scenario'])}</td>"
            f"<td>{html.escape(row['variant'])}</td>"
            f"<td>{html.escape(row['model'])}</td>"
            f"<td>{row['count']}</td>"
            f"<td>{row['success_rate']:.0%}</td>"
            f"<td>{row['correct_completion_rate']:.0%}</td>"
            f"{quality_cell}"
            f"{p50_cell}"
            f"{p95_cell}"
            f"{p99_cell}"
            f"<td>{html.escape(str(row.get('control_variant') or '-'))}</td>"
            f"{change_cell}"
            f"<td>{html.escape(str(row.get('overall_control_variant') or '-'))}</td>"
            f"{overall_change_cell}"
            f"<td>{len(errors)}</td>"
            "</tr>"
        )
        if p50 is not None:
            width = 700 * float(p50) / max_p50
            y = 28 * index
            label = html.escape(f"{row['scenario']} / {row['variant']}")
            bars.append(
                f'<text x="0" y="{y + 15}" font-size="12">{label}</text>'
                f'<rect x="250" y="{y}" width="{width:.1f}" height="18" fill="#2563eb"/>'
                f'<text x="{255 + width:.1f}" y="{y + 14}" font-size="11">{p50:.0f} ms</text>'
            )

    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>AI response performance report</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #172033; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border-bottom: 1px solid #d7deea; padding: .55rem; text-align: left; }}
    th {{ background: #eef3fb; }}
    .chart {{ overflow-x: auto; margin: 2rem 0; }}
  </style>
</head>
<body>
  <h1>AI response performance report</h1>
  <p>Latency is reported only for successful calls. Quality and errors remain visible.</p>
  <div class="chart">
    <svg width="1100" height="{max(50, len(bars) * 28)}" role="img"
         aria-label="Median latency by benchmark case">{"".join(bars)}</svg>
  </div>
  <table>
    <thead><tr><th>Scenario</th><th>Variant</th><th>Model</th><th>N</th>
      <th>Success</th><th>Correct</th><th>Quality</th><th>p50 ms</th>
      <th>p95 ms</th><th>p99 ms</th><th>Control</th>
      <th>p50 change [95% CI]</th><th>Overall control</th>
      <th>Overall p50 change [95% CI]</th><th>Errors</th></tr></thead>
    <tbody>{"".join(rows)}</tbody>
  </table>
</body>
</html>
"""
    path.write_text(document, encoding="utf-8")
