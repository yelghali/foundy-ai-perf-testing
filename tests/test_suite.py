from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, cast

import pytest
from openai import AsyncOpenAI

from ai_perf import suite
from ai_perf.config import AzureOpenAISettings
from ai_perf.models import Observation, TokenUsage
from ai_perf.scenarios import BenchmarkCase


def test_priority_case_uses_supported_deployment() -> None:
    settings = AzureOpenAISettings(
        endpoint="https://example.openai.azure.com",
        deployment="baseline",
        fast_deployment="fast",
        priority_deployment="priority-supported",
    )

    assert (
        suite.model_for_case(
            settings,
            BenchmarkCase(
                "text_chat",
                "bundle-best-priority",
                deployment_role="priority",
            ),
        )
        == "priority-supported"
    )


@pytest.mark.asyncio
async def test_case_group_records_requested_concurrency(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def capture(
        settings: Any,
        client: Any,
        case: Any,
        *,
        mcp_connection: Any,
        fixture_index: int,
    ) -> Observation:
        del settings, client, case, mcp_connection
        return Observation(
            run_id="run",
            scenario="text_chat",
            variant="baseline",
            model="test",
            started_at=Observation.started_now(),
            total_ms=1,
            first_token_ms=None,
            output_tokens_per_second=None,
            usage=TokenUsage(),
            response_text="ok",
            metadata={"fixture_index_seen": fixture_index},
        )

    monkeypatch.setattr(suite, "_capture_case", capture)
    observations = await suite._run_case_group(
        cast(AzureOpenAISettings, object()),
        cast(AsyncOpenAI, object()),
        BenchmarkCase("text_chat", "baseline"),
        warmups=0,
        repetitions=2,
        concurrency=2,
        output=tmp_path / "observations.jsonl",
        mcp_connection=None,
    )

    assert [observation.metadata["concurrency"] for observation in observations] == [2, 2]
    assert [observation.metadata["fixture_index_seen"] for observation in observations] == [
        0,
        1,
    ]
    assert all(observation.metadata["batch_size"] == 2 for observation in observations)
    assert all(
        observation.metadata["throughput_requests_per_second"] > 0
        for observation in observations
    )


@pytest.mark.asyncio
async def test_interleaved_schedule_is_balanced_and_reproducible(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def capture(
        settings: Any,
        client: Any,
        case: BenchmarkCase,
        *,
        mcp_connection: Any,
        fixture_index: int,
    ) -> Observation:
        del settings, client, mcp_connection
        return Observation(
            run_id=f"{case.variant}-{fixture_index}",
            scenario=case.scenario,
            variant=case.variant,
            model="test",
            started_at=Observation.started_now(),
            total_ms=fixture_index + 1,
            first_token_ms=None,
            output_tokens_per_second=None,
            usage=TokenUsage(),
            response_text="ok",
            quality_passed=True,
            metadata={"fixture_index": fixture_index},
        )

    monkeypatch.setattr(suite, "_capture_case", capture)
    cases = [
        BenchmarkCase("text_chat", "baseline"),
        BenchmarkCase("text_chat", "concise-output"),
        BenchmarkCase("text_chat", "reduced-input"),
    ]
    first = await suite._run_interleaved(
        cast(AzureOpenAISettings, object()),
        cast(AsyncOpenAI, object()),
        cases,
        warmups=0,
        repetitions=4,
        output=tmp_path / "first.jsonl",
        schedule_seed=42,
    )
    second = await suite._run_interleaved(
        cast(AzureOpenAISettings, object()),
        cast(AsyncOpenAI, object()),
        cases,
        warmups=0,
        repetitions=4,
        output=tmp_path / "second.jsonl",
        schedule_seed=42,
    )

    first_order = [
        (item.metadata["round"], item.metadata["position_in_round"], item.variant)
        for item in first
    ]
    second_order = [
        (item.metadata["round"], item.metadata["position_in_round"], item.variant)
        for item in second
    ]
    assert first_order == second_order
    for round_index in range(4):
        round_variants = {
            item.variant for item in first if item.metadata["round"] == round_index
        }
        assert round_variants == {case.variant for case in cases}
    assert {item.metadata["fixture_index"] for item in first} == {0, 1, 2, 3}


@pytest.mark.asyncio
async def test_new_client_case_includes_client_setup_in_end_to_end_latency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    @asynccontextmanager
    async def client_context(settings: Any) -> Any:
        del settings
        yield object()

    async def run_case(
        client: Any,
        model: str,
        case: BenchmarkCase,
        *,
        mcp_connection: Any,
        fixture_index: int,
    ) -> Observation:
        del client, model, case, mcp_connection, fixture_index
        return Observation(
            run_id="run",
            scenario="text_chat",
            variant="new-client-per-request",
            model="test",
            started_at=Observation.started_now(),
            total_ms=100,
            first_token_ms=40,
            output_tokens_per_second=20,
            usage=TokenUsage(),
            response_text="ok",
            quality_passed=True,
            timings_ms={"model_total": 100},
        )

    times = iter((10.0, 10.25))
    monkeypatch.setattr(suite, "create_client", client_context)
    monkeypatch.setattr(suite, "run_case", run_case)
    monkeypatch.setattr(suite.time, "perf_counter", lambda: next(times))
    settings = AzureOpenAISettings(
        endpoint="https://example.openai.azure.com",
        deployment="test",
    )
    case = BenchmarkCase("text_chat", "new-client-per-request", reuse_client=False)

    observation = await suite._capture_case(
        settings,
        cast(AsyncOpenAI, object()),
        case,
        mcp_connection=None,
    )

    assert observation.total_ms == 250
    assert observation.first_token_ms == 190
    assert observation.timings_ms["client_setup"] == 150
