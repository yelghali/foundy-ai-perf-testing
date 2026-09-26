from __future__ import annotations

import asyncio
import platform
import random
import time
import uuid
from collections.abc import Sequence
from contextlib import AsyncExitStack
from dataclasses import replace
from importlib.metadata import version
from pathlib import Path
from typing import Literal

from openai import AsyncOpenAI

from ai_perf.client import create_client
from ai_perf.config import AzureOpenAISettings
from ai_perf.mcp_client import (
    MCPConnection,
    open_foundry_toolbox_connection,
    open_mcp_connection,
    open_remote_mcp_connection,
)
from ai_perf.models import Observation, TokenUsage
from ai_perf.results import append_observation
from ai_perf.scenarios import BenchmarkCase, run_case

RUNTIME_METADATA = {
    "python_version": platform.python_version(),
    "openai_sdk_version": version("openai"),
    "api": "responses_v1",
}

ExecutionSchedule = Literal["grouped", "interleaved"]


def model_for_case(settings: AzureOpenAISettings, case: BenchmarkCase) -> str:
    if case.deployment_role == "baseline":
        return settings.deployment
    if case.deployment_role == "fast":
        if settings.fast_deployment is None:
            raise ValueError(f"Case {case.variant} requires AZURE_OPENAI_FAST_DEPLOYMENT")
        return settings.fast_deployment
    if settings.priority_deployment is None:
        raise ValueError(
            f"Case {case.variant} requires AZURE_OPENAI_PRIORITY_DEPLOYMENT"
        )
    return settings.priority_deployment


async def _capture_case(
    settings: AzureOpenAISettings,
    shared_client: AsyncOpenAI,
    case: BenchmarkCase,
    *,
    mcp_connection: MCPConnection | None,
    fixture_index: int = 0,
) -> Observation:
    model = model_for_case(settings, case)
    started_at = Observation.started_now()
    started = time.perf_counter()
    try:
        if case.reuse_client:
            observation = await run_case(
                shared_client,
                model,
                case,
                mcp_connection=mcp_connection,
                fixture_index=fixture_index,
            )
        else:
            async with create_client(settings) as one_shot_client:
                observation = await run_case(
                    one_shot_client,
                    model,
                    case,
                    mcp_connection=mcp_connection,
                    fixture_index=fixture_index,
                )
                end_to_end_ms = (time.perf_counter() - started) * 1000
                client_setup_ms = max(0.0, end_to_end_ms - observation.total_ms)
                observation = replace(
                    observation,
                    total_ms=end_to_end_ms,
                    first_token_ms=(
                        observation.first_token_ms + client_setup_ms
                        if observation.first_token_ms is not None
                        else None
                    ),
                    timings_ms={
                        **observation.timings_ms,
                        "client_setup": client_setup_ms,
                    },
                )
        return replace(
            observation,
            metadata={
                **observation.metadata,
                **RUNTIME_METADATA,
                "azure_region": settings.azure_region,
                "benchmark_image": settings.benchmark_image,
                "fixture_index": fixture_index,
            },
        )
    except Exception as error:
        return Observation(
            run_id=str(uuid.uuid4()),
            scenario=case.scenario,
            variant=case.variant,
            model=model,
            started_at=started_at,
            total_ms=(time.perf_counter() - started) * 1000,
            first_token_ms=None,
            output_tokens_per_second=None,
            usage=TokenUsage(),
            response_text="",
            success=False,
            service_tier_requested=case.service_tier,
            metadata={
                **RUNTIME_METADATA,
                "azure_region": settings.azure_region,
                "benchmark_image": settings.benchmark_image,
                "fixture_index": fixture_index,
            },
            error_type=type(error).__name__,
            error_message=str(error),
        )


async def _run_case_group(
    settings: AzureOpenAISettings,
    client: AsyncOpenAI,
    case: BenchmarkCase,
    *,
    warmups: int,
    repetitions: int,
    concurrency: int,
    output: Path,
    mcp_connection: MCPConnection | None,
) -> list[Observation]:
    for warmup_index in range(warmups):
        warmup = await _capture_case(
            settings,
            client,
            case,
            mcp_connection=mcp_connection,
            fixture_index=warmup_index,
        )
        if not warmup.success:
            failed_warmup = replace(
                warmup,
                metadata={
                    **warmup.metadata,
                    "phase": "warmup",
                    "concurrency": concurrency,
                },
            )
            append_observation(output, failed_warmup)
            return [failed_warmup]

    semaphore = asyncio.Semaphore(concurrency)

    async def measured_call(measurement_index: int) -> Observation:
        async with semaphore:
            observation = await _capture_case(
                settings,
                client,
                case,
                mcp_connection=mcp_connection,
                fixture_index=measurement_index,
            )
            return replace(
                observation,
                metadata={
                    **observation.metadata,
                    "concurrency": concurrency,
                    "schedule": "grouped",
                    "measurement_index": measurement_index,
                },
            )

    batch_started = time.perf_counter()
    observations = await asyncio.gather(
        *(measured_call(index) for index in range(repetitions))
    )
    batch_elapsed_ms = (time.perf_counter() - batch_started) * 1000
    throughput = repetitions / (batch_elapsed_ms / 1000)
    observations = [
        replace(
            observation,
            metadata={
                **observation.metadata,
                "batch_size": repetitions,
                "batch_elapsed_ms": batch_elapsed_ms,
                "throughput_requests_per_second": throughput,
            },
        )
        for observation in observations
    ]
    for observation in observations:
        append_observation(output, observation)
    return observations


def _connection_key(case: BenchmarkCase) -> tuple[str, int, str] | None:
    if case.tool_transport in {"mcp_warm", "mcp_remote", "foundry_toolbox_search"}:
        return (case.tool_transport, case.tool_count, case.description_style)
    return None


async def _open_interleaved_connections(
    stack: AsyncExitStack,
    settings: AzureOpenAISettings,
    cases: Sequence[BenchmarkCase],
) -> dict[tuple[str, int, str], MCPConnection]:
    connections: dict[tuple[str, int, str], MCPConnection] = {}
    for case in cases:
        key = _connection_key(case)
        if key is None or key in connections:
            continue
        if case.tool_transport == "mcp_warm":
            context = open_mcp_connection(case.tool_count, case.description_style)
        elif case.tool_transport == "mcp_remote":
            if settings.remote_mcp_url is None:
                raise ValueError("mcp_remote requires AI_PERF_REMOTE_MCP_URL")
            context = open_remote_mcp_connection(settings.remote_mcp_url)
        else:
            if settings.foundry_toolbox_endpoint is None:
                raise ValueError(
                    "foundry_toolbox_search requires AI_PERF_TOOLBOX_ENDPOINT"
                )
            context = open_foundry_toolbox_connection(
                settings.foundry_toolbox_endpoint,
                managed_identity_client_id=settings.managed_identity_client_id,
                token_scope=settings.foundry_token_scope,
            )
        connections[key] = await stack.enter_async_context(context)
    return connections


async def _run_interleaved(
    settings: AzureOpenAISettings,
    client: AsyncOpenAI,
    cases: Sequence[BenchmarkCase],
    *,
    warmups: int,
    repetitions: int,
    output: Path,
    schedule_seed: int,
) -> list[Observation]:
    rng = random.Random(schedule_seed)
    all_observations: list[Observation] = []
    async with AsyncExitStack() as stack:
        connections = await _open_interleaved_connections(stack, settings, cases)

        for warmup_index in range(warmups):
            warmup_cases = list(cases)
            rng.shuffle(warmup_cases)
            for case in warmup_cases:
                warmup = await _capture_case(
                    settings,
                    client,
                    case,
                    mcp_connection=connections.get(_connection_key(case)),
                    fixture_index=warmup_index,
                )
                if not warmup.success:
                    raise RuntimeError(
                        f"Warm-up failed for {case.scenario}/{case.variant}: "
                        f"{warmup.error_type}: {warmup.error_message}"
                    )

        for round_index in range(repetitions):
            round_cases = list(cases)
            rng.shuffle(round_cases)
            for position, case in enumerate(round_cases):
                observation = await _capture_case(
                    settings,
                    client,
                    case,
                    mcp_connection=connections.get(_connection_key(case)),
                    fixture_index=round_index,
                )
                observation = replace(
                    observation,
                    metadata={
                        **observation.metadata,
                        "concurrency": 1,
                        "schedule": "interleaved",
                        "schedule_seed": schedule_seed,
                        "round": round_index,
                        "position_in_round": position,
                        "block_size": len(cases),
                    },
                )
                append_observation(output, observation)
                all_observations.append(observation)
    return all_observations


async def execute_suite(
    settings: AzureOpenAISettings,
    cases: Sequence[BenchmarkCase],
    *,
    warmups: int,
    repetitions: int,
    concurrency: int,
    output: Path,
    schedule: ExecutionSchedule = "grouped",
    schedule_seed: int = 20260904,
) -> list[Observation]:
    if warmups < 0:
        raise ValueError("warmups must be zero or greater")
    if repetitions < 1:
        raise ValueError("repetitions must be at least one")
    if concurrency < 1:
        raise ValueError("concurrency must be at least one")
    if schedule not in {"grouped", "interleaved"}:
        raise ValueError("schedule must be 'grouped' or 'interleaved'")
    if schedule == "interleaved" and concurrency != 1:
        raise ValueError("interleaved scheduling requires concurrency 1")
    if output.exists():
        raise FileExistsError(f"Refusing to append a new suite to existing file: {output}")

    all_observations: list[Observation] = []
    async with create_client(settings) as client:
        if schedule == "interleaved":
            return await _run_interleaved(
                settings,
                client,
                cases,
                warmups=warmups,
                repetitions=repetitions,
                output=output,
                schedule_seed=schedule_seed,
            )
        for case in cases:
            if case.tool_transport == "mcp_warm":
                async with open_mcp_connection(
                    case.tool_count,
                    case.description_style,
                ) as connection:
                    observations = await _run_case_group(
                        settings,
                        client,
                        case,
                        warmups=warmups,
                        repetitions=repetitions,
                        concurrency=concurrency,
                        output=output,
                        mcp_connection=connection,
                    )
            elif case.tool_transport == "mcp_remote":
                if settings.remote_mcp_url is None:
                    raise ValueError("mcp_remote requires AI_PERF_REMOTE_MCP_URL")
                async with open_remote_mcp_connection(settings.remote_mcp_url) as connection:
                    observations = await _run_case_group(
                        settings,
                        client,
                        case,
                        warmups=warmups,
                        repetitions=repetitions,
                        concurrency=concurrency,
                        output=output,
                        mcp_connection=connection,
                    )
            elif case.tool_transport == "foundry_toolbox_search":
                if settings.foundry_toolbox_endpoint is None:
                    raise ValueError(
                        "foundry_toolbox_search requires AI_PERF_TOOLBOX_ENDPOINT"
                    )
                async with open_foundry_toolbox_connection(
                    settings.foundry_toolbox_endpoint,
                    managed_identity_client_id=settings.managed_identity_client_id,
                    token_scope=settings.foundry_token_scope,
                ) as connection:
                    observations = await _run_case_group(
                        settings,
                        client,
                        case,
                        warmups=warmups,
                        repetitions=repetitions,
                        concurrency=concurrency,
                        output=output,
                        mcp_connection=connection,
                    )
            else:
                observations = await _run_case_group(
                    settings,
                    client,
                    case,
                    warmups=warmups,
                    repetitions=repetitions,
                    concurrency=concurrency,
                    output=output,
                    mcp_connection=None,
                )
            all_observations.extend(observations)
    return all_observations
