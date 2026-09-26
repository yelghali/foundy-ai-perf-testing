from __future__ import annotations

import json
import math
import random
from collections.abc import Iterable, Sequence
from pathlib import Path
from statistics import mean, median
from typing import Any

from ai_perf.models import Observation


def append_observation(path: Path, observation: Observation) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as output:
        output.write(json.dumps(observation.to_dict(), ensure_ascii=False) + "\n")


def load_observations(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as source:
        return [json.loads(line) for line in source if line.strip()]


def percentile(values: Sequence[float], probability: float) -> float:
    if not values:
        raise ValueError("Cannot calculate a percentile for an empty sequence")
    if not 0 <= probability <= 1:
        raise ValueError("Percentile probability must be between 0 and 1")

    ordered = sorted(values)
    rank = max(1, math.ceil(probability * len(ordered)))
    return ordered[rank - 1]


def summarize_total_latency(observations: Iterable[dict[str, Any]]) -> dict[str, float | int]:
    values = [float(observation["total_ms"]) for observation in observations]
    if not values:
        raise ValueError("No observations to summarize")

    return {
        "count": len(values),
        "mean_ms": mean(values),
        "p50_ms": median(values),
        "p95_ms": percentile(values, 0.95),
        "p99_ms": percentile(values, 0.99),
    }


def bootstrap_median_ci(
    values: Sequence[float],
    *,
    confidence: float = 0.95,
    resamples: int = 5000,
    seed: int = 20260904,
) -> tuple[float, float]:
    if not values:
        raise ValueError("Cannot bootstrap an empty sequence")
    if not 0 < confidence < 1:
        raise ValueError("confidence must be between zero and one")
    if resamples < 1:
        raise ValueError("resamples must be at least one")

    rng = random.Random(seed)
    sample_size = len(values)
    estimates = [
        median(values[rng.randrange(sample_size)] for _ in range(sample_size))
        for _ in range(resamples)
    ]
    tail = (1 - confidence) / 2
    return percentile(estimates, tail), percentile(estimates, 1 - tail)


def bootstrap_median_comparison(
    treatment: Sequence[float],
    control: Sequence[float],
    *,
    paired: bool,
    confidence: float = 0.95,
    resamples: int = 5000,
    seed: int = 20260904,
) -> dict[str, tuple[float, float]]:
    if not treatment or not control:
        raise ValueError("Treatment and control values are required")
    if paired and len(treatment) != len(control):
        raise ValueError("Paired treatment and control values must have the same length")

    rng = random.Random(seed)
    delta_estimates: list[float] = []
    percent_estimates: list[float] = []
    treatment_size = len(treatment)
    control_size = len(control)
    for _ in range(resamples):
        if paired:
            indices = [rng.randrange(treatment_size) for _ in range(treatment_size)]
            treatment_sample = [treatment[index] for index in indices]
            control_sample = [control[index] for index in indices]
        else:
            treatment_sample = [
                treatment[rng.randrange(treatment_size)] for _ in range(treatment_size)
            ]
            control_sample = [control[rng.randrange(control_size)] for _ in range(control_size)]
        treatment_median = median(treatment_sample)
        control_median = median(control_sample)
        delta_estimates.append(treatment_median - control_median)
        percent_estimates.append(
            100 * (treatment_median - control_median) / control_median
        )

    tail = (1 - confidence) / 2
    return {
        "delta_ms": (
            percentile(delta_estimates, tail),
            percentile(delta_estimates, 1 - tail),
        ),
        "change_percent": (
            percentile(percent_estimates, tail),
            percentile(percent_estimates, 1 - tail),
        ),
    }
