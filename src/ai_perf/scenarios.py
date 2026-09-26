from __future__ import annotations

import asyncio
import json
import random
import time
import uuid
from dataclasses import dataclass
from typing import Any, Literal

from openai import AsyncOpenAI

from ai_perf.fixtures import (
    benchmark_document_pages,
    benchmark_document_text,
    benchmark_pdf_data_uri,
    document_fixture,
    receipt_fixture,
    receipt_image_data_uri,
    text_fixture,
    tool_fixture,
)
from ai_perf.mcp_client import MCPConnection, open_mcp_connection
from ai_perf.models import Observation, TokenUsage
from ai_perf.quality import QualityResult, score_fields, score_term_groups, score_terms
from ai_perf.runner import ResponseMeasurement, extract_usage, measure_response
from ai_perf.tool_catalogue import (
    DescriptionStyle,
    SchemaStyle,
    build_tool_specs,
    execute_tool,
    serialize_tool_result,
)

ScenarioName = Literal["text_chat", "image_understanding", "file_processing", "tool_calling"]
DeploymentRole = Literal["baseline", "fast", "priority"]
CacheMode = Literal["none", "cold", "warm"]
ToolTransport = Literal[
    "native",
    "mcp_warm",
    "mcp_cold",
    "mcp_remote",
    "foundry_toolbox_search",
]
ImageDetail = Literal["high", "low", "cascade"]
FileInput = Literal["pdf", "extracted_text", "sequential_pages", "parallel_pages"]


@dataclass(frozen=True)
class BenchmarkCase:
    scenario: ScenarioName
    variant: str
    deployment_role: DeploymentRole = "baseline"
    max_output_tokens: int = 200
    service_tier: str | None = None
    stream: bool = True
    reduced_input: bool = False
    concise_output: bool = False
    cache_mode: CacheMode = "none"
    reuse_client: bool = True
    prompt_override: str | None = None
    tool_count: int = 20
    description_style: DescriptionStyle = "concise"
    schema_style: SchemaStyle = "simple"
    ambiguous_tools: bool = False
    reorder_tools: bool = False
    tool_transport: ToolTransport = "native"
    sequential_tools: bool = False
    parallel_tools: bool = False
    image_detail: ImageDetail = "high"
    file_input: FileInput = "pdf"


def cases_for_profile(
    profile: str,
    *,
    has_fast_deployment: bool,
    has_toolbox_comparison: bool = False,
    has_priority_deployment: bool = False,
) -> list[BenchmarkCase]:
    smoke = [
        BenchmarkCase("text_chat", "baseline"),
        BenchmarkCase("image_understanding", "baseline", stream=False),
        BenchmarkCase("file_processing", "baseline", stream=False),
        BenchmarkCase("tool_calling", "native-baseline", stream=False),
        BenchmarkCase(
            "tool_calling",
            "mcp-warm",
            stream=False,
            tool_transport="mcp_warm",
        ),
    ]
    if has_toolbox_comparison:
        smoke.extend(
            [
                BenchmarkCase(
                    "tool_calling",
                    "mcp-remote-50",
                    stream=False,
                    tool_count=50,
                    tool_transport="mcp_remote",
                ),
                BenchmarkCase(
                    "tool_calling",
                    "foundry-toolbox-search-50",
                    stream=False,
                    tool_count=50,
                    tool_transport="foundry_toolbox_search",
                ),
            ]
        )
    if profile == "smoke":
        return smoke
    if profile == "bundle":
        if not has_priority_deployment:
            raise ValueError(
                "bundle profile requires AZURE_OPENAI_PRIORITY_DEPLOYMENT"
            )
        return _bundle_cases()
    if profile != "screen":
        raise ValueError("profile must be 'smoke', 'screen', or 'bundle'")

    cases: list[BenchmarkCase] = []
    for scenario in ("text_chat", "image_understanding", "file_processing", "tool_calling"):
        stream = scenario == "text_chat"
        baseline_variant = "native-baseline" if scenario == "tool_calling" else "baseline"
        cases.extend(
            [
                BenchmarkCase(scenario, baseline_variant, stream=stream),
                BenchmarkCase(
                    scenario,
                    "concise-output",
                    max_output_tokens=80,
                    stream=stream,
                    concise_output=True,
                ),
                BenchmarkCase(
                    scenario,
                    "reduced-input",
                    stream=stream,
                    reduced_input=True,
                    tool_count=5,
                ),
                BenchmarkCase(
                    scenario,
                    "new-client-per-request",
                    stream=stream,
                    reuse_client=False,
                ),
                BenchmarkCase(
                    scenario,
                    "cache-cold",
                    stream=stream,
                    cache_mode="cold",
                ),
                BenchmarkCase(
                    scenario,
                    "cache-warm",
                    stream=stream,
                    cache_mode="warm",
                ),
                BenchmarkCase(
                    scenario,
                    "priority",
                    stream=stream,
                    service_tier="priority",
                ),
            ]
        )
        if has_fast_deployment:
            cases.append(
                BenchmarkCase(
                    scenario,
                    "fast-model",
                    deployment_role="fast",
                    stream=stream,
                )
            )

    cases.extend(
        [
            BenchmarkCase("text_chat", "non-streaming", stream=False),
            BenchmarkCase(
                "tool_calling",
                "mcp-warm",
                stream=False,
                tool_transport="mcp_warm",
            ),
            BenchmarkCase(
                "tool_calling",
                "mcp-cold",
                stream=False,
                tool_transport="mcp_cold",
            ),
            BenchmarkCase(
                "tool_calling",
                "fifty-tools",
                stream=False,
                tool_count=50,
            ),
            BenchmarkCase(
                "tool_calling",
                "minimal-descriptions",
                stream=False,
                description_style="minimal",
            ),
            BenchmarkCase(
                "tool_calling",
                "verbose-descriptions",
                stream=False,
                description_style="verbose",
            ),
            BenchmarkCase(
                "tool_calling",
                "sequential-tools",
                stream=False,
                sequential_tools=True,
            ),
            BenchmarkCase(
                "tool_calling",
                "parallel-tools",
                stream=False,
                parallel_tools=True,
            ),
            BenchmarkCase(
                "image_understanding",
                "low-detail",
                stream=False,
                image_detail="low",
            ),
            BenchmarkCase(
                "image_understanding",
                "low-detail-cascade",
                stream=False,
                image_detail="cascade",
            ),
            BenchmarkCase(
                "file_processing",
                "extracted-text",
                stream=False,
                file_input="extracted_text",
            ),
            BenchmarkCase(
                "file_processing",
                "sequential-pages",
                stream=False,
                file_input="sequential_pages",
            ),
            BenchmarkCase(
                "file_processing",
                "parallel-pages",
                stream=False,
                file_input="parallel_pages",
            ),
            BenchmarkCase(
                "tool_calling",
                "many-parameter-schema",
                stream=False,
                schema_style="many_parameters",
            ),
            BenchmarkCase(
                "tool_calling",
                "nested-schema",
                stream=False,
                schema_style="nested",
            ),
            BenchmarkCase(
                "tool_calling",
                "ambiguous-descriptions",
                stream=False,
                ambiguous_tools=True,
            ),
            BenchmarkCase(
                "tool_calling",
                "reordered-definitions",
                stream=False,
                cache_mode="warm",
                reorder_tools=True,
            ),
        ]
    )
    if has_toolbox_comparison:
        cases.extend(
            [
                BenchmarkCase(
                    "tool_calling",
                    "mcp-remote-50",
                    stream=False,
                    tool_count=50,
                    tool_transport="mcp_remote",
                ),
                BenchmarkCase(
                    "tool_calling",
                    "foundry-toolbox-search-50",
                    stream=False,
                    tool_count=50,
                    tool_transport="foundry_toolbox_search",
                ),
            ]
        )
    return cases


def _bundle_cases() -> list[BenchmarkCase]:
    cases: list[BenchmarkCase] = []
    for scenario in (
        "text_chat",
        "image_understanding",
        "file_processing",
        "tool_calling",
    ):
        common: dict[str, Any] = {
            "deployment_role": "priority",
            "stream": False,
        }
        if scenario == "text_chat":
            worst = {
                "cache_mode": "cold",
                "max_output_tokens": 200,
            }
            best = {
                "cache_mode": "warm",
                "concise_output": True,
                "max_output_tokens": 80,
            }
        elif scenario == "image_understanding":
            worst = {
                "cache_mode": "cold",
                "image_detail": "high",
                "max_output_tokens": 200,
            }
            best = {
                "cache_mode": "warm",
                "image_detail": "low",
                "concise_output": True,
                "max_output_tokens": 80,
            }
        elif scenario == "file_processing":
            worst = {"file_input": "pdf"}
            best = {"file_input": "extracted_text"}
        else:
            worst = {
                "tool_count": 20,
                "description_style": "concise",
                "sequential_tools": True,
            }
            best = {
                "tool_count": 5,
                "description_style": "minimal",
                "parallel_tools": True,
            }

        cases.extend(
            [
                BenchmarkCase(
                    scenario,
                    "bundle-worst-standard",
                    service_tier="default",
                    **common,
                    **worst,
                ),
                BenchmarkCase(
                    scenario,
                    "bundle-best-standard",
                    service_tier="default",
                    **common,
                    **best,
                ),
                BenchmarkCase(
                    scenario,
                    "bundle-best-priority",
                    service_tier="priority",
                    **common,
                    **best,
                ),
            ]
        )
    return cases


def _long_instructions(scenario: str) -> str:
    sentence = (
        f"For the {scenario} benchmark, follow the output contract exactly, preserve supplied "
        "identifiers and numeric values, avoid invented facts, and answer only from the input. "
    )
    return sentence * 120


def _apply_cache_options(request: dict[str, Any], case: BenchmarkCase) -> None:
    if case.cache_mode == "none":
        return
    suffix = "stable" if case.cache_mode == "warm" else str(uuid.uuid4())
    request["prompt_cache_key"] = f"ai-perf-{case.scenario}-{suffix}"
    request["prompt_cache_retention"] = "in_memory"


def _instructions_for_case(case: BenchmarkCase, default: str) -> str:
    if case.cache_mode == "none":
        return default
    instructions = _long_instructions(case.scenario)
    if case.cache_mode == "cold":
        return f"Cache isolation nonce: {uuid.uuid4()}\n{instructions}"
    return instructions


def _apply_service_tier(request: dict[str, Any], case: BenchmarkCase) -> None:
    if case.service_tier is not None:
        request["service_tier"] = case.service_tier


def _json_format(
    name: str,
    properties: dict[str, Any],
    required: list[str],
) -> dict[str, Any]:
    return {
        "format": {
            "type": "json_schema",
            "name": name,
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": properties,
                "required": required,
            },
        }
    }


def _observation(
    case: BenchmarkCase,
    model: str,
    started_at: str,
    measurement: ResponseMeasurement,
    quality: QualityResult,
    *,
    timings_ms: dict[str, float] | None = None,
    metadata: dict[str, Any] | None = None,
) -> Observation:
    return Observation(
        run_id=str(uuid.uuid4()),
        scenario=case.scenario,
        variant=case.variant,
        model=model,
        started_at=started_at,
        total_ms=measurement.total_ms,
        first_token_ms=measurement.first_token_ms,
        output_tokens_per_second=measurement.output_tokens_per_second,
        usage=measurement.usage,
        response_text=measurement.response_text,
        quality_score=quality.score,
        quality_passed=quality.passed,
        service_tier_requested=case.service_tier,
        service_tier_actual=measurement.service_tier_actual,
        timings_ms=timings_ms or {"model_total": measurement.total_ms},
        metadata={
            "deployment_role": case.deployment_role,
            "stream": case.stream,
            "max_output_tokens": case.max_output_tokens,
            "cache_mode": case.cache_mode,
            "reuse_client": case.reuse_client,
            "concise_output": case.concise_output,
            "reduced_input": case.reduced_input,
            **(metadata or {}),
            "quality": quality.details,
        },
    )


async def run_case(
    client: AsyncOpenAI,
    model: str,
    case: BenchmarkCase,
    *,
    mcp_connection: MCPConnection | None = None,
    fixture_index: int = 0,
) -> Observation:
    if case.scenario == "text_chat":
        return await _run_text(client, model, case, fixture_index=fixture_index)
    if case.scenario == "image_understanding":
        return await _run_image(client, model, case, fixture_index=fixture_index)
    if case.scenario == "file_processing":
        return await _run_file(client, model, case, fixture_index=fixture_index)
    if case.scenario == "tool_calling":
        return await _run_tools(
            client,
            model,
            case,
            mcp_connection=mcp_connection,
            fixture_index=fixture_index,
        )
    raise ValueError(f"Unsupported scenario: {case.scenario}")


async def _run_text(
    client: AsyncOpenAI,
    model: str,
    case: BenchmarkCase,
    *,
    fixture_index: int,
) -> Observation:
    started_at = Observation.started_now()
    fixture = text_fixture(fixture_index)
    if case.prompt_override is not None:
        user_prompt = case.prompt_override
        messages: Any = user_prompt
        required_terms = ("95", "tail", "user", "capacity")
    else:
        user_prompt = fixture.prompt
        required_terms = fixture.required_terms
        if case.concise_output:
            user_prompt += " Answer in no more than two sentences."
        else:
            user_prompt += " Answer in four concise bullet points."
        history = [
            {
                "role": "user" if index % 2 == 0 else "assistant",
                "content": (
                    f"Earlier conversation turn {index}: application configuration context that "
                    "is not needed for the current latency question."
                ),
            }
            for index in range(12)
        ]
        messages = [
            *([] if case.reduced_input else history),
            {"role": "user", "content": user_prompt},
        ]

    request: dict[str, Any] = {
        "model": model,
        "input": messages,
        "max_output_tokens": case.max_output_tokens,
        "instructions": _instructions_for_case(
            case,
            "Answer accurately and follow the requested format.",
        ),
    }
    _apply_cache_options(request, case)
    _apply_service_tier(request, case)
    measurement = await measure_response(client, request, stream=case.stream)
    quality = score_terms(measurement.response_text, required_terms)
    return _observation(
        case,
        model,
        started_at,
        measurement,
        quality,
        metadata={"fixture_id": fixture.fixture_id},
    )


async def _run_image(
    client: AsyncOpenAI,
    model: str,
    case: BenchmarkCase,
    *,
    fixture_index: int,
) -> Observation:
    started_at = Observation.started_now()
    fixture = receipt_fixture(fixture_index)
    expected = {
        "invoice_id": fixture.invoice_id,
        "total": fixture.total,
        "status": fixture.status,
    }
    properties: dict[str, Any] = {
        "invoice_id": {"type": "string"},
        "total": {"type": "number"},
        "status": {"type": "string"},
    }
    required = list(properties)
    if not case.concise_output:
        properties["explanation"] = {"type": "string"}
        required.append("explanation")

    def request_for(detail: Literal["low", "high"]) -> dict[str, Any]:
        request: dict[str, Any] = {
            "model": model,
            "instructions": _instructions_for_case(
                case,
                "Extract values exactly from the supplied benchmark receipt.",
            ),
            "input": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": "Extract the invoice ID, total, and status.",
                        },
                        {
                            "type": "input_image",
                            "image_url": receipt_image_data_uri(
                                reduced=case.reduced_input,
                                fixture_index=fixture_index,
                            ),
                            "detail": detail,
                        },
                    ],
                }
            ],
            "text": _json_format("receipt", properties, required),
            "max_output_tokens": case.max_output_tokens,
        }
        _apply_cache_options(request, case)
        _apply_service_tier(request, case)
        return request

    if case.image_detail != "cascade":
        measurement = await measure_response(
            client,
            request_for(case.image_detail),
            stream=case.stream,
        )
        quality = score_fields(measurement.response_text, expected)
        timings_ms = None
        escalated = False
    else:
        cascade_started = time.perf_counter()
        low_measurement = await measure_response(
            client,
            request_for("low"),
            stream=case.stream,
        )
        quality = score_fields(low_measurement.response_text, expected)
        timings_ms = {"low_detail": low_measurement.total_ms}
        escalated = not quality.passed
        if not escalated:
            measurement = low_measurement
        else:
            high_measurement = await measure_response(
                client,
                request_for("high"),
                stream=case.stream,
            )
            quality = score_fields(high_measurement.response_text, expected)
            timings_ms["high_detail"] = high_measurement.total_ms
            measurement = ResponseMeasurement(
                response=high_measurement.response,
                response_text=high_measurement.response_text,
                total_ms=(time.perf_counter() - cascade_started) * 1000,
                first_token_ms=high_measurement.first_token_ms,
                output_tokens_per_second=high_measurement.output_tokens_per_second,
                usage=low_measurement.usage + high_measurement.usage,
                service_tier_actual=high_measurement.service_tier_actual,
            )

    return _observation(
        case,
        model,
        started_at,
        measurement,
        quality,
        timings_ms=timings_ms,
        metadata={
            "image_detail": case.image_detail,
            "image_resized": case.reduced_input,
            "cascade_escalated": escalated,
            "fixture_id": fixture.fixture_id,
        },
    )


async def _run_file(
    client: AsyncOpenAI,
    model: str,
    case: BenchmarkCase,
    *,
    fixture_index: int,
) -> Observation:
    started_at = Observation.started_now()
    fixture = document_fixture(fixture_index)
    expected = {
        "project_code": fixture.project_code,
        "approved_budget": fixture.approved_budget,
    }

    if case.file_input in {"sequential_pages", "parallel_pages"}:
        page_properties: dict[str, Any] = {
            "project_code": {"type": ["string", "null"]},
            "approved_budget": {"type": ["number", "null"]},
        }

        async def process_page(page_number: int, page: str) -> ResponseMeasurement:
            request: dict[str, Any] = {
                "model": model,
                "instructions": (
                    "Extract exact values from this page. Use null when a requested value "
                    "does not appear on the page."
                ),
                "input": (
                    f"Page {page_number}:\n{page}\n\n"
                    "Extract the project code and approved budget."
                ),
                "text": _json_format(
                    "performance_report_page",
                    page_properties,
                    list(page_properties),
                ),
                "max_output_tokens": case.max_output_tokens,
            }
            _apply_service_tier(request, case)
            return await measure_response(client, request, stream=case.stream)

        pages = benchmark_document_pages(fixture_index)
        processing_started = time.perf_counter()
        if case.file_input == "parallel_pages":
            measurements = list(
                await asyncio.gather(
                    *(
                        process_page(index, page)
                        for index, page in enumerate(pages, start=1)
                    )
                )
            )
        else:
            measurements = [
                await process_page(index, page)
                for index, page in enumerate(pages, start=1)
            ]
        total_ms = (time.perf_counter() - processing_started) * 1000
        qualities = [
            score_fields(measurement.response_text, expected)
            for measurement in measurements
        ]
        best_index = max(range(len(qualities)), key=lambda index: qualities[index].score)
        selected = measurements[best_index]
        combined_usage = measurements[0].usage
        for page_measurement in measurements[1:]:
            combined_usage += page_measurement.usage
        measurement = ResponseMeasurement(
            response=selected.response,
            response_text=selected.response_text,
            total_ms=total_ms,
            first_token_ms=None,
            output_tokens_per_second=None,
            usage=combined_usage,
            service_tier_actual=next(
                (
                    item.service_tier_actual
                    for item in measurements
                    if item.service_tier_actual is not None
                ),
                None,
            ),
        )
        return _observation(
            case,
            model,
            started_at,
            measurement,
            qualities[best_index],
            timings_ms={
                f"page_{index}": item.total_ms
                for index, item in enumerate(measurements, start=1)
            },
            metadata={
                "pages": len(pages),
                "file_input": case.file_input,
                "selected_page": best_index + 1,
                "fixture_id": fixture.fixture_id,
            },
        )

    properties: dict[str, Any] = {
        "project_code": {"type": "string"},
        "approved_budget": {"type": "number"},
    }
    required = list(properties)
    if not case.concise_output:
        properties["explanation"] = {"type": "string"}
        required.append("explanation")

    if case.file_input == "extracted_text":
        content: list[dict[str, Any]] = [
            {
                "type": "input_text",
                "text": (
                    "Extracted document text:\n"
                    f"{benchmark_document_text(fixture_index=fixture_index)}\n\n"
                    "Extract the project code and approved budget."
                ),
            }
        ]
    else:
        content = [
            {
                "type": "input_file",
                "filename": "performance-report.pdf",
                "file_data": benchmark_pdf_data_uri(
                    relevant_page_only=case.reduced_input,
                    fixture_index=fixture_index,
                ),
            },
            {
                "type": "input_text",
                "text": "Extract the project code and approved budget.",
            },
        ]

    request: dict[str, Any] = {
        "model": model,
        "instructions": _instructions_for_case(
            case,
            "Extract exact values from the supplied benchmark PDF.",
        ),
        "input": [
            {
                "role": "user",
                "content": content,
            }
        ],
        "text": _json_format("performance_report", properties, required),
        "max_output_tokens": case.max_output_tokens,
    }
    _apply_cache_options(request, case)
    _apply_service_tier(request, case)
    measurement = await measure_response(client, request, stream=case.stream)
    quality = score_fields(measurement.response_text, expected)
    return _observation(
        case,
        model,
        started_at,
        measurement,
        quality,
        metadata={
            "pages": 1 if case.reduced_input else 3,
            "file_input": case.file_input,
            "fixture_id": fixture.fixture_id,
        },
    )


async def _run_tools(
    client: AsyncOpenAI,
    model: str,
    case: BenchmarkCase,
    *,
    mcp_connection: MCPConnection | None,
    fixture_index: int,
) -> Observation:
    if case.tool_transport == "foundry_toolbox_search":
        if mcp_connection is None:
            raise ValueError("foundry_toolbox_search requires a reused toolbox connection")
        return await _run_foundry_toolbox_core(
            client,
            model,
            case,
            connection=mcp_connection,
            fixture_index=fixture_index,
        )
    if case.tool_transport == "mcp_cold":
        overall_started = time.perf_counter()
        async with open_mcp_connection(case.tool_count, case.description_style) as connection:
            return await _run_tool_core(
                client,
                model,
                case,
                connection=connection,
                overall_started=overall_started,
                discovery_ms=connection.discovery_ms,
                fixture_index=fixture_index,
            )
    if case.tool_transport == "mcp_warm":
        if mcp_connection is None:
            raise ValueError("mcp_warm requires a reused MCP connection")
        return await _run_tool_core(
            client,
            model,
            case,
            connection=mcp_connection,
            discovery_ms=0.0,
            fixture_index=fixture_index,
        )
    if case.tool_transport == "mcp_remote":
        if mcp_connection is None:
            raise ValueError("mcp_remote requires a reused remote MCP connection")
        return await _run_tool_core(
            client,
            model,
            case,
            connection=mcp_connection,
            discovery_ms=0.0,
            fixture_index=fixture_index,
        )
    return await _run_tool_core(client, model, case, fixture_index=fixture_index)


async def _run_foundry_toolbox_core(
    client: AsyncOpenAI,
    model: str,
    case: BenchmarkCase,
    *,
    connection: MCPConnection,
    fixture_index: int = 0,
) -> Observation:
    started_at = Observation.started_now()
    overall_started = time.perf_counter()
    tools = connection.tools
    fixture = tool_fixture(fixture_index)
    prompt = (
        f"Use the toolbox to get the benchmark {fixture.capability} for {fixture.city}. "
        "If the needed tool is not listed, first call tool_search to discover it. Then use "
        "call_tool to invoke the discovered tool and answer with the requested value."
    )
    request: dict[str, Any] = {
        "model": model,
        "input": prompt,
        "tools": tools,
        "parallel_tool_calls": False,
        "max_output_tokens": case.max_output_tokens,
    }
    responses: list[Any] = []
    called_names: list[str] = []
    call_arguments: list[dict[str, Any]] = []
    timings_ms: dict[str, float] = {"mcp_discovery": 0.0}
    current_model_stage = "tool_search_selection"

    for _ in range(4):
        model_started = time.perf_counter()
        response = await client.responses.create(**request)
        model_ms = (time.perf_counter() - model_started) * 1000
        timings_ms[current_model_stage] = timings_ms.get(current_model_stage, 0.0) + model_ms
        responses.append(response)
        function_calls = [
            item for item in response.output if getattr(item, "type", None) == "function_call"
        ]
        if not function_calls:
            break

        outputs: list[dict[str, Any]] = []
        executed_names: set[str] = set()
        for call in function_calls:
            arguments = json.loads(call.arguments)
            if not isinstance(arguments, dict):
                raise TypeError(f"Tool arguments for {call.name} were not an object")
            called_names.append(call.name)
            call_arguments.append(arguments)
            executed_names.add(call.name)

            execution_started = time.perf_counter()
            result = await connection.call_tool_result(call.name, arguments)
            execution_ms = (time.perf_counter() - execution_started) * 1000
            execution_stage = (
                "tool_search_execution" if call.name == "tool_search" else "tool_execution"
            )
            timings_ms[execution_stage] = (
                timings_ms.get(execution_stage, 0.0) + execution_ms
            )
            outputs.append(
                {
                    "type": "function_call_output",
                    "call_id": call.call_id,
                    "output": result.model_dump_json(by_alias=True, exclude_none=True),
                }
            )

        current_model_stage = (
            "tool_selection" if "tool_search" in executed_names else "final_generation"
        )
        request = {
            "model": model,
            "previous_response_id": response.id,
            "input": outputs,
            "tools": tools,
            "parallel_tool_calls": False,
            "max_output_tokens": case.max_output_tokens,
        }
    else:
        raise RuntimeError("Foundry toolbox interaction exceeded four model steps")

    if not called_names:
        raise RuntimeError("The model did not call a Foundry toolbox tool")

    final_response = responses[-1]
    expected_selected = any(fixture.expected_tool in name for name in called_names) or any(
        fixture.expected_tool in json.dumps(arguments, sort_keys=True)
        for arguments in call_arguments
    )
    text_quality = score_term_groups(
        final_response.output_text,
        {"requested_value": fixture.expected_terms},
    )
    quality = QualityResult(
        score=(float(expected_selected) + text_quality.score) / 2,
        passed=expected_selected and text_quality.passed,
        details={
            "called_tools": called_names,
            "expected_tool": fixture.expected_tool,
            "expected_tool_selected": expected_selected,
            "answer": text_quality.details,
        },
    )
    usage = TokenUsage()
    for response in responses:
        usage += extract_usage(response)
    actual_tier = next(
        (
            tier
            for tier in (
                getattr(response, "service_tier", None) for response in reversed(responses)
            )
            if tier is not None
        ),
        None,
    )
    total_ms = (time.perf_counter() - overall_started) * 1000
    measurement = ResponseMeasurement(
        response=final_response,
        response_text=final_response.output_text,
        total_ms=total_ms,
        first_token_ms=None,
        output_tokens_per_second=None,
        usage=usage,
        service_tier_actual=actual_tier,
    )
    return _observation(
        case,
        model,
        started_at,
        measurement,
        quality,
        timings_ms=timings_ms,
        metadata={
            "tool_count": case.tool_count,
            "initial_tool_count": len(tools),
            "initial_tool_names": [str(tool["name"]) for tool in tools],
            "tool_definition_bytes": len(
                json.dumps(tools, separators=(",", ":"), sort_keys=True).encode("utf-8")
            ),
            "description_style": case.description_style,
            "schema_style": case.schema_style,
            "transport": case.tool_transport,
            "model_call_count": len(responses),
            "toolbox_calls": called_names,
            "tool_search_used": "tool_search" in called_names,
            "connection_discovery_ms": connection.discovery_ms,
            "fixture_id": fixture.fixture_id,
        },
    )


async def _run_tool_core(
    client: AsyncOpenAI,
    model: str,
    case: BenchmarkCase,
    *,
    connection: MCPConnection | None = None,
    overall_started: float | None = None,
    discovery_ms: float = 0.0,
    fixture_index: int = 0,
) -> Observation:
    if case.sequential_tools and case.parallel_tools:
        raise ValueError("A tool case cannot be both sequential and parallel")

    started_at = Observation.started_now()
    overall_started = overall_started if overall_started is not None else time.perf_counter()
    fixture = tool_fixture(fixture_index)
    if connection is None:
        specs = build_tool_specs(
            case.tool_count,
            case.description_style,
            schema_style=case.schema_style,
            ambiguous=case.ambiguous_tools,
        )
        if case.reorder_tools:
            random.SystemRandom().shuffle(specs)
        tools = [spec.as_openai_tool() for spec in specs]
    else:
        tools = connection.tools

    multi_tool = case.sequential_tools or case.parallel_tools
    if multi_tool:
        prompt = (
            f"Use both lookup_weather and get_local_time for {fixture.city}, then summarize "
            "the temperature and local time."
        )
        expected_names = {"lookup_weather", "get_local_time"}
        required_term_groups = {
            "temperature": ("21",),
            "local_time": ("14:30", "2:30 pm", "2:30 p.m."),
        }
    else:
        prompt = (
            f"Use the correct tool to get the benchmark {fixture.capability} for "
            f"{fixture.city}, then answer with the requested value."
        )
        expected_names = {fixture.expected_tool}
        required_term_groups = {"requested_value": fixture.expected_terms}

    selection_request: dict[str, Any] = {
        "model": model,
        "input": prompt,
        "tools": tools,
        "parallel_tool_calls": case.parallel_tools,
        "max_output_tokens": case.max_output_tokens,
    }
    if case.cache_mode != "none":
        selection_request["instructions"] = _instructions_for_case(case, "")
    _apply_cache_options(selection_request, case)
    _apply_service_tier(selection_request, case)

    async def invoke(call: Any) -> tuple[Any, dict[str, Any]]:
        arguments = json.loads(call.arguments)
        if not isinstance(arguments, dict):
            raise TypeError(f"Tool arguments for {call.name} were not an object")
        if connection is None:
            result = execute_tool(call.name, arguments)
        else:
            result = await connection.call_tool(call.name, arguments)
        return call, result

    request = selection_request
    responses: list[Any] = []
    called_names: list[str] = []
    selection_ms = 0.0
    execution_ms = 0.0
    final_ms = 0.0
    final_response: Any = None

    for _ in range(4):
        model_started = time.perf_counter()
        response = await client.responses.create(**request)
        selection_ms += (time.perf_counter() - model_started) * 1000
        responses.append(response)
        function_calls = [
            item for item in response.output if getattr(item, "type", None) == "function_call"
        ]
        if not function_calls:
            if not called_names:
                raise RuntimeError("The model did not produce a function call")
            final_response = response
            break

        calls_to_execute = function_calls if case.parallel_tools else function_calls[:1]
        execution_started = time.perf_counter()
        if case.parallel_tools:
            executed = await asyncio.gather(*(invoke(call) for call in calls_to_execute))
        else:
            executed = [await invoke(calls_to_execute[0])]
        execution_ms += (time.perf_counter() - execution_started) * 1000
        called_names.extend(call.name for call, _ in executed)
        outputs = [
            {
                "type": "function_call_output",
                "call_id": call.call_id,
                "output": serialize_tool_result(result),
            }
            for call, result in executed
        ]

        continue_selecting = case.sequential_tools and not expected_names.issubset(
            called_names
        )
        request = {
            "model": model,
            "previous_response_id": response.id,
            "input": outputs,
            "max_output_tokens": 80 if case.concise_output else case.max_output_tokens,
        }
        if continue_selecting:
            request["tools"] = tools
            request["parallel_tool_calls"] = False
        else:
            _apply_service_tier(request, case)
            final_started = time.perf_counter()
            final_response = await client.responses.create(**request)
            final_ms = (time.perf_counter() - final_started) * 1000
            responses.append(final_response)
            break
        _apply_service_tier(request, case)
    else:
        raise RuntimeError("Tool interaction exceeded four selection steps")

    if final_response is None:
        raise RuntimeError("Tool interaction ended without a final response")

    total_ms = (time.perf_counter() - overall_started) * 1000

    text_quality = score_term_groups(final_response.output_text, required_term_groups)
    selection_correct = set(called_names) == expected_names
    quality = QualityResult(
        score=(float(selection_correct) + text_quality.score) / 2,
        passed=selection_correct and text_quality.passed,
        details={
            "called_tools": called_names,
            "expected_tools": sorted(expected_names),
            "answer": text_quality.details,
        },
    )
    usage = TokenUsage()
    for response in responses:
        usage += extract_usage(response)
    actual_tier = next(
        (
            tier
            for tier in (
                getattr(response, "service_tier", None) for response in reversed(responses)
            )
            if tier is not None
        ),
        None,
    )
    measurement = ResponseMeasurement(
        response=final_response,
        response_text=final_response.output_text,
        total_ms=total_ms,
        first_token_ms=None,
        output_tokens_per_second=None,
        usage=usage,
        service_tier_actual=actual_tier,
    )
    return _observation(
        case,
        model,
        started_at,
        measurement,
        quality,
        timings_ms={
            "mcp_discovery": discovery_ms,
            "tool_selection": selection_ms,
            "tool_execution": execution_ms,
            "final_generation": final_ms,
        },
        metadata={
            "tool_count": len(tools),
            "tool_definition_bytes": len(
                json.dumps(tools, separators=(",", ":"), sort_keys=True).encode("utf-8")
            ),
            "description_style": case.description_style,
            "schema_style": case.schema_style,
            "ambiguous_tools": case.ambiguous_tools,
            "tool_order": "randomized" if case.reorder_tools else "stable",
            "transport": case.tool_transport,
            "sequential_tools": case.sequential_tools,
            "parallel_tools": case.parallel_tools,
            "tool_execution_mode": (
                "parallel"
                if case.parallel_tools
                else "sequential"
                if case.sequential_tools
                else "single"
            ),
            "model_call_count": len(responses),
            "fixture_id": fixture.fixture_id,
        },
    )
