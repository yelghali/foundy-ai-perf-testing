from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class QualityResult:
    score: float
    passed: bool
    details: dict[str, Any]


def score_terms(
    text: str, required_terms: tuple[str, ...], threshold: float = 0.75
) -> QualityResult:
    normalized = text.casefold()
    matches = {term: term.casefold() in normalized for term in required_terms}
    score = sum(matches.values()) / len(matches)
    return QualityResult(score=score, passed=score >= threshold, details={"terms": matches})


def score_term_groups(
    text: str,
    required_groups: dict[str, tuple[str, ...]],
) -> QualityResult:
    normalized = text.casefold()
    matches = {
        name: {
            "matched": any(term.casefold() in normalized for term in alternatives),
            "alternatives": alternatives,
        }
        for name, alternatives in required_groups.items()
    }
    score = sum(bool(result["matched"]) for result in matches.values()) / len(matches)
    return QualityResult(
        score=score,
        passed=score == 1.0,
        details={"term_groups": matches},
    )


def parse_json_output(text: str) -> dict[str, Any]:
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("Expected the model response to be a JSON object")
    return value


def score_fields(text: str, expected: dict[str, Any]) -> QualityResult:
    try:
        actual = parse_json_output(text)
    except (json.JSONDecodeError, ValueError) as error:
        return QualityResult(
            score=0.0,
            passed=False,
            details={"parse_error": str(error), "expected": expected},
        )

    matches = {key: actual.get(key) == value for key, value in expected.items()}
    score = sum(matches.values()) / len(matches)
    return QualityResult(
        score=score,
        passed=score == 1.0,
        details={"matches": matches, "actual": actual},
    )
