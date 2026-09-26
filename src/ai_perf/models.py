from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    cached_tokens: int | None = None
    reasoning_tokens: int | None = None

    def __add__(self, other: TokenUsage) -> TokenUsage:
        def add_optional(left: int | None, right: int | None) -> int | None:
            if left is None and right is None:
                return None
            return (left or 0) + (right or 0)

        return TokenUsage(
            input_tokens=add_optional(self.input_tokens, other.input_tokens),
            output_tokens=add_optional(self.output_tokens, other.output_tokens),
            cached_tokens=add_optional(self.cached_tokens, other.cached_tokens),
            reasoning_tokens=add_optional(self.reasoning_tokens, other.reasoning_tokens),
        )


@dataclass(frozen=True)
class Observation:
    run_id: str
    scenario: str
    variant: str
    model: str
    started_at: str
    total_ms: float
    first_token_ms: float | None
    output_tokens_per_second: float | None
    usage: TokenUsage
    response_text: str
    success: bool = True
    quality_score: float | None = None
    quality_passed: bool | None = None
    service_tier_requested: str | None = None
    service_tier_actual: str | None = None
    timings_ms: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    error_type: str | None = None
    error_message: str | None = None

    @classmethod
    def started_now(cls) -> str:
        return datetime.now(UTC).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
