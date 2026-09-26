import json
from types import SimpleNamespace
from typing import Any, cast

import pytest
from openai import AsyncOpenAI

from ai_perf.mcp_client import MCPConnection
from ai_perf.scenarios import (
    BenchmarkCase,
    _run_foundry_toolbox_core,
    _run_tool_core,
    cases_for_profile,
)


def test_screen_covers_scenario_specific_performance_levers() -> None:
    cases = cases_for_profile("screen", has_fast_deployment=True)
    variants = {(case.scenario, case.variant) for case in cases}

    assert len(cases) == 49
    assert len(variants) == len(cases)
    assert {
        ("image_understanding", "low-detail"),
        ("image_understanding", "low-detail-cascade"),
        ("file_processing", "extracted-text"),
        ("file_processing", "sequential-pages"),
        ("file_processing", "parallel-pages"),
        ("tool_calling", "many-parameter-schema"),
        ("tool_calling", "nested-schema"),
        ("tool_calling", "ambiguous-descriptions"),
        ("tool_calling", "reordered-definitions"),
        ("tool_calling", "sequential-tools"),
        ("tool_calling", "parallel-tools"),
    } <= variants


def test_image_input_reduction_does_not_also_change_detail() -> None:
    cases = cases_for_profile("screen", has_fast_deployment=True)
    reduced_image = next(
        case
        for case in cases
        if case.scenario == "image_understanding" and case.variant == "reduced-input"
    )

    assert reduced_image.reduced_input is True
    assert reduced_image.image_detail == "high"


def test_toolbox_configuration_adds_controlled_remote_comparison() -> None:
    cases = cases_for_profile(
        "screen",
        has_fast_deployment=True,
        has_toolbox_comparison=True,
    )
    variants = {case.variant: case for case in cases}

    assert len(cases) == 51
    assert variants["mcp-remote-50"].tool_count == 50
    assert variants["mcp-remote-50"].tool_transport == "mcp_remote"
    assert variants["foundry-toolbox-search-50"].tool_count == 50
    assert (
        variants["foundry-toolbox-search-50"].tool_transport
        == "foundry_toolbox_search"
    )


def test_bundle_profile_combines_only_supported_winners() -> None:
    cases = cases_for_profile(
        "bundle",
        has_fast_deployment=True,
        has_priority_deployment=True,
    )

    assert len(cases) == 12
    assert {case.deployment_role for case in cases} == {"priority"}
    assert {case.stream for case in cases} == {False}
    for scenario in {
        "text_chat",
        "image_understanding",
        "file_processing",
        "tool_calling",
    }:
        scenario_cases = [case for case in cases if case.scenario == scenario]
        assert [case.variant for case in scenario_cases] == [
            "bundle-worst-standard",
            "bundle-best-standard",
            "bundle-best-priority",
        ]
        assert [case.service_tier for case in scenario_cases] == [
            "default",
            "default",
            "priority",
        ]

    text_best = next(
        case
        for case in cases
        if case.scenario == "text_chat"
        and case.variant == "bundle-best-standard"
    )
    assert text_best.cache_mode == "warm"
    assert text_best.concise_output is True
    assert text_best.max_output_tokens == 80

    image_best = next(
        case
        for case in cases
        if case.scenario == "image_understanding"
        and case.variant == "bundle-best-standard"
    )
    assert image_best.cache_mode == "warm"
    assert image_best.image_detail == "low"
    assert image_best.concise_output is True

    file_best = next(
        case
        for case in cases
        if case.scenario == "file_processing"
        and case.variant == "bundle-best-standard"
    )
    assert file_best.file_input == "extracted_text"

    tool_worst = next(
        case
        for case in cases
        if case.scenario == "tool_calling"
        and case.variant == "bundle-worst-standard"
    )
    tool_best = next(
        case
        for case in cases
        if case.scenario == "tool_calling"
        and case.variant == "bundle-best-standard"
    )
    assert tool_worst.sequential_tools is True
    assert tool_worst.tool_count == 20
    assert tool_best.parallel_tools is True
    assert tool_best.tool_count == 5
    assert tool_best.description_style == "minimal"


def test_bundle_profile_requires_priority_deployment() -> None:
    with pytest.raises(
        ValueError,
        match="AZURE_OPENAI_PRIORITY_DEPLOYMENT",
    ):
        cases_for_profile("bundle", has_fast_deployment=True)


class FakeToolResult:
    def __init__(self, value: dict[str, Any]) -> None:
        self.value = value

    def model_dump_json(self, **_: object) -> str:
        return json.dumps(self.value)


class FakeToolboxConnection:
    def __init__(self) -> None:
        self.tools = [
            {"type": "function", "name": "tool_search", "parameters": {}},
            {"type": "function", "name": "call_tool", "parameters": {}},
        ]
        self.discovery_ms = 12.5
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def call_tool_result(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> FakeToolResult:
        self.calls.append((name, arguments))
        if name == "tool_search":
            return FakeToolResult({"tools": [{"name": "lookup_weather"}]})
        return FakeToolResult({"temperature_c": 21})


class FakeResponses:
    def __init__(self) -> None:
        usage = SimpleNamespace(
            input_tokens=10,
            output_tokens=5,
            input_tokens_details=SimpleNamespace(cached_tokens=0),
            output_tokens_details=SimpleNamespace(reasoning_tokens=0),
        )
        self.responses = [
            SimpleNamespace(
                id="search",
                output=[
                    SimpleNamespace(
                        type="function_call",
                        name="tool_search",
                        arguments='{"query":"weather temperature city","limit":5}',
                        call_id="search-call",
                    )
                ],
                output_text="",
                usage=usage,
                service_tier="default",
            ),
            SimpleNamespace(
                id="call",
                output=[
                    SimpleNamespace(
                        type="function_call",
                        name="call_tool",
                        arguments=(
                            '{"name":"lookup_weather",'
                            '"arguments":{"query":"Paris"}}'
                        ),
                        call_id="tool-call",
                    )
                ],
                output_text="",
                usage=usage,
                service_tier="default",
            ),
            SimpleNamespace(
                id="final",
                output=[],
                output_text="The benchmark temperature in Paris is 21 C.",
                usage=usage,
                service_tier="default",
            ),
        ]
        self.requests: list[dict[str, Any]] = []

    async def create(self, **request: Any) -> Any:
        self.requests.append(request)
        return self.responses.pop(0)


@pytest.mark.asyncio
async def test_foundry_toolbox_runs_search_call_and_final_generation() -> None:
    responses = FakeResponses()
    connection = FakeToolboxConnection()
    client = SimpleNamespace(responses=responses)
    case = BenchmarkCase(
        "tool_calling",
        "foundry-toolbox-search-50",
        stream=False,
        tool_count=50,
        tool_transport="foundry_toolbox_search",
    )

    observation = await _run_foundry_toolbox_core(
        cast(AsyncOpenAI, client),
        "test-model",
        case,
        connection=cast(MCPConnection, connection),
    )

    assert observation.quality_passed is True
    assert observation.usage.input_tokens == 30
    assert observation.usage.output_tokens == 15
    assert observation.metadata["initial_tool_count"] == 2
    assert observation.metadata["tool_search_used"] is True
    assert observation.metadata["model_call_count"] == 3
    assert [name for name, _ in connection.calls] == ["tool_search", "call_tool"]
    assert set(observation.timings_ms) == {
        "mcp_discovery",
        "tool_search_selection",
        "tool_search_execution",
        "tool_selection",
        "tool_execution",
        "final_generation",
    }


@pytest.mark.asyncio
async def test_foundry_toolbox_accepts_direct_discovered_tool_call() -> None:
    responses = FakeResponses()
    responses.responses[1].output[0].name = "benchmark___lookup_weather"
    responses.responses[1].output[0].arguments = '{"query":"Paris"}'
    connection = FakeToolboxConnection()
    client = SimpleNamespace(responses=responses)
    case = BenchmarkCase(
        "tool_calling",
        "foundry-toolbox-search-50",
        stream=False,
        tool_count=50,
        tool_transport="foundry_toolbox_search",
    )

    observation = await _run_foundry_toolbox_core(
        cast(AsyncOpenAI, client),
        "test-model",
        case,
        connection=cast(MCPConnection, connection),
    )

    assert observation.quality_passed is True
    assert observation.metadata["toolbox_calls"] == [
        "tool_search",
        "benchmark___lookup_weather",
    ]


@pytest.mark.asyncio
async def test_foundry_toolbox_scores_time_fixture() -> None:
    responses = FakeResponses()
    responses.responses[0].output[0].arguments = (
        '{"query":"benchmark local time city","limit":5}'
    )
    responses.responses[1].output[0].arguments = (
        '{"name":"get_local_time","arguments":{"query":"Berlin"}}'
    )
    responses.responses[2].output_text = "The benchmark local time in Berlin is 14:30."
    connection = FakeToolboxConnection()
    client = SimpleNamespace(responses=responses)
    case = BenchmarkCase(
        "tool_calling",
        "foundry-toolbox-search-50",
        stream=False,
        tool_count=50,
        tool_transport="foundry_toolbox_search",
    )

    observation = await _run_foundry_toolbox_core(
        cast(AsyncOpenAI, client),
        "test-model",
        case,
        connection=cast(MCPConnection, connection),
        fixture_index=1,
    )

    assert observation.quality_passed is True
    assert observation.metadata["fixture_id"] == "tool-time-berlin"


@pytest.mark.asyncio
async def test_sequential_tools_use_two_selection_rounds() -> None:
    usage = SimpleNamespace(
        input_tokens=10,
        output_tokens=5,
        input_tokens_details=SimpleNamespace(cached_tokens=0),
        output_tokens_details=SimpleNamespace(reasoning_tokens=0),
    )
    responses = FakeResponses()
    responses.responses = [
        SimpleNamespace(
            id="weather",
            output=[
                SimpleNamespace(
                    type="function_call",
                    name="lookup_weather",
                    arguments='{"query":"Paris"}',
                    call_id="weather-call",
                )
            ],
            output_text="",
            usage=usage,
            service_tier="default",
        ),
        SimpleNamespace(
            id="time",
            output=[
                SimpleNamespace(
                    type="function_call",
                    name="get_local_time",
                    arguments='{"query":"Paris"}',
                    call_id="time-call",
                )
            ],
            output_text="",
            usage=usage,
            service_tier="default",
        ),
        SimpleNamespace(
            id="final",
            output=[],
            output_text="Paris is 21 C and the local time is 14:30.",
            usage=usage,
            service_tier="default",
        ),
    ]
    client = SimpleNamespace(responses=responses)
    case = BenchmarkCase(
        "tool_calling",
        "sequential-tools",
        stream=False,
        sequential_tools=True,
    )

    observation = await _run_tool_core(
        cast(AsyncOpenAI, client),
        "test-model",
        case,
    )

    assert observation.quality_passed is True
    assert observation.metadata["model_call_count"] == 3
    assert observation.metadata["tool_execution_mode"] == "sequential"
    assert observation.metadata["quality"]["called_tools"] == [
        "lookup_weather",
        "get_local_time",
    ]
