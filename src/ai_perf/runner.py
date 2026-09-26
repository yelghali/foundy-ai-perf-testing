from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from openai import AsyncOpenAI

from ai_perf.models import TokenUsage


@dataclass(frozen=True)
class ResponseMeasurement:
    response: Any
    response_text: str
    total_ms: float
    first_token_ms: float | None
    output_tokens_per_second: float | None
    usage: TokenUsage
    service_tier_actual: str | None


async def measure_response(
    client: AsyncOpenAI,
    request: dict[str, Any],
    *,
    stream: bool,
) -> ResponseMeasurement:
    request = {**request, "stream": stream}
    started = time.perf_counter()

    if not stream:
        response = await client.responses.create(**request)
        total_ms = (time.perf_counter() - started) * 1000
        return ResponseMeasurement(
            response=response,
            response_text=response.output_text,
            total_ms=total_ms,
            first_token_ms=None,
            output_tokens_per_second=None,
            usage=extract_usage(response),
            service_tier_actual=getattr(response, "service_tier", None),
        )

    first_token_ms: float | None = None
    response_text_parts: list[str] = []
    completed_response: Any = None
    stream_result = await client.responses.create(**request)
    async for event in stream_result:
        if event.type == "response.output_text.delta":
            if first_token_ms is None:
                first_token_ms = (time.perf_counter() - started) * 1000
            response_text_parts.append(event.delta)
        elif event.type == "response.completed":
            completed_response = event.response

    if completed_response is None:
        raise RuntimeError("Streaming response ended without a response.completed event")

    total_ms = (time.perf_counter() - started) * 1000
    usage = extract_usage(completed_response)
    output_rate = None
    if usage.output_tokens and first_token_ms is not None and total_ms > first_token_ms:
        output_rate = usage.output_tokens / ((total_ms - first_token_ms) / 1000)

    return ResponseMeasurement(
        response=completed_response,
        response_text="".join(response_text_parts),
        total_ms=total_ms,
        first_token_ms=first_token_ms,
        output_tokens_per_second=output_rate,
        usage=usage,
        service_tier_actual=getattr(completed_response, "service_tier", None),
    )


def extract_usage(response: Any) -> TokenUsage:
    usage = getattr(response, "usage", None)
    if usage is None:
        return TokenUsage()

    input_details = getattr(usage, "input_tokens_details", None)
    output_details = getattr(usage, "output_tokens_details", None)
    return TokenUsage(
        input_tokens=getattr(usage, "input_tokens", None),
        output_tokens=getattr(usage, "output_tokens", None),
        cached_tokens=getattr(input_details, "cached_tokens", None),
        reasoning_tokens=getattr(output_details, "reasoning_tokens", None),
    )


class ResponsesBenchmarkRunner:
    def __init__(self, client: AsyncOpenAI, model: str) -> None:
        self._client = client
        self._model = model

    async def run_text(
        self,
        *,
        prompt: str,
        variant: str,
        max_output_tokens: int,
        service_tier: str | None = None,
    ) -> Any:
        from ai_perf.scenarios import BenchmarkCase, run_case

        case = BenchmarkCase(
            scenario="text_chat",
            variant=variant,
            deployment_role="baseline",
            max_output_tokens=max_output_tokens,
            service_tier=service_tier,
            prompt_override=prompt,
        )
        return await run_case(self._client, self._model, case)
