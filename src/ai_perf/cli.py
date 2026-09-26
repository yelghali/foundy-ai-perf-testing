from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from ai_perf.client import create_client
from ai_perf.config import AzureOpenAISettings
from ai_perf.foundry_toolbox import provision_toolbox
from ai_perf.reporting import build_summary, write_html_report, write_summary_json
from ai_perf.results import append_observation, load_observations, summarize_total_latency
from ai_perf.runner import ResponsesBenchmarkRunner
from ai_perf.scenarios import cases_for_profile
from ai_perf.storage import upload_artifacts
from ai_perf.suite import execute_suite

DEFAULT_PROMPT = (
    "Explain in four concise bullet points why measuring p95 latency matters for an AI application."
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AI response performance benchmark")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_text = subparsers.add_parser("run-text", help="Run the streaming text baseline")
    run_text.add_argument("--prompt", default=DEFAULT_PROMPT)
    run_text.add_argument("--variant", default="baseline")
    run_text.add_argument("--warmups", type=int, default=3)
    run_text.add_argument("--repetitions", type=int, default=10)
    run_text.add_argument("--max-output-tokens", type=int, default=200)
    run_text.add_argument("--service-tier")
    run_text.add_argument("--output", type=Path)

    summarize = subparsers.add_parser("summarize", help="Summarize a JSONL result file")
    summarize.add_argument("path", type=Path)

    run_suite = subparsers.add_parser("run-suite", help="Run a cross-scenario benchmark suite")
    run_suite.add_argument(
        "--profile",
        choices=("smoke", "screen", "bundle"),
        default="smoke",
    )
    run_suite.add_argument("--warmups", type=int, default=1)
    run_suite.add_argument("--repetitions", type=int, default=2)
    run_suite.add_argument("--concurrency", type=int, default=1)
    run_suite.add_argument(
        "--schedule",
        choices=("grouped", "interleaved"),
        default="grouped",
        help="Use interleaved for randomized complete-block publication runs",
    )
    run_suite.add_argument("--seed", type=int, default=20260904)
    run_suite.add_argument("--output", type=Path)
    run_suite.add_argument("--report", type=Path)
    run_suite.add_argument("--upload", action="store_true")
    run_suite.add_argument("--continue-on-case-error", action="store_true")
    run_suite.add_argument(
        "--scenario",
        action="append",
        choices=("text_chat", "image_understanding", "file_processing", "tool_calling"),
    )
    run_suite.add_argument("--variant", action="append")

    subparsers.add_parser(
        "provision-toolbox",
        help="Create the Foundry toolbox-search benchmark if it does not exist",
    )
    return parser


def _positive_or_zero(value: int, name: str) -> None:
    if value < 0:
        raise ValueError(f"{name} must be zero or greater")


async def run_text(args: argparse.Namespace) -> None:
    _positive_or_zero(args.warmups, "warmups")
    if args.repetitions < 1:
        raise ValueError("repetitions must be at least one")
    if args.max_output_tokens < 1:
        raise ValueError("max-output-tokens must be at least one")

    settings = AzureOpenAISettings.from_env()
    output = args.output or settings.results_dir / (
        f"text-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.jsonl"
    )
    async with create_client(settings) as client:
        runner = ResponsesBenchmarkRunner(client, settings.deployment)
        for _ in range(args.warmups):
            await runner.run_text(
                prompt=args.prompt,
                variant=args.variant,
                max_output_tokens=args.max_output_tokens,
                service_tier=args.service_tier,
            )

        for _ in range(args.repetitions):
            observation = await runner.run_text(
                prompt=args.prompt,
                variant=args.variant,
                max_output_tokens=args.max_output_tokens,
                service_tier=args.service_tier,
            )
            append_observation(output, observation)

    summary = summarize_total_latency(load_observations(output))
    print(json.dumps({"output": str(output), "summary": summary}, indent=2))


async def run_suite_command(args: argparse.Namespace) -> None:
    settings = AzureOpenAISettings.from_env()
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output = args.output or settings.results_dir / f"{args.profile}-{timestamp}.jsonl"
    report = args.report or settings.results_dir.parent / "reports" / (
        f"{args.profile}-{timestamp}.html"
    )
    summary_path = report.with_suffix(".json")
    cases = cases_for_profile(
        args.profile,
        has_fast_deployment=settings.fast_deployment is not None,
        has_toolbox_comparison=settings.has_toolbox_comparison,
        has_priority_deployment=settings.has_priority_deployment,
    )
    if args.scenario:
        cases = [case for case in cases if case.scenario in args.scenario]
    if args.variant:
        cases = [case for case in cases if case.variant in args.variant]
    if not cases:
        raise ValueError("The scenario and variant filters selected no benchmark cases")
    observations = await execute_suite(
        settings,
        cases,
        warmups=args.warmups,
        repetitions=args.repetitions,
        concurrency=args.concurrency,
        output=output,
        schedule=args.schedule,
        schedule_seed=args.seed,
    )
    loaded = load_observations(output)
    summary = build_summary(loaded)
    write_html_report(report, summary)
    write_summary_json(summary_path, summary)

    uploaded: list[str] = []
    if args.upload:
        uploaded = await upload_artifacts(
            settings,
            (output, report, summary_path),
            prefix=timestamp,
        )
    errors = [observation for observation in observations if not observation.success]
    quality_failures = [
        observation for observation in observations if observation.quality_passed is False
    ]
    result = {
        "output": str(output),
        "report": str(report),
        "summary": str(summary_path),
        "cases": len(cases),
        "observations": len(observations),
        "warmups": args.warmups,
        "repetitions": args.repetitions,
        "concurrency": args.concurrency,
        "schedule": args.schedule,
        "seed": args.seed,
        "errors": len(errors),
        "quality_failures": len(quality_failures),
        "uploaded": uploaded,
        "results": summary,
    }
    print(json.dumps(result, indent=2))
    if errors and not args.continue_on_case_error:
        raise RuntimeError(f"{len(errors)} benchmark observations failed; inspect {summary_path}")


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "run-text":
        asyncio.run(run_text(args))
    elif args.command == "run-suite":
        asyncio.run(run_suite_command(args))
    elif args.command == "summarize":
        print(json.dumps(summarize_total_latency(load_observations(args.path)), indent=2))
    elif args.command == "provision-toolbox":
        print(json.dumps(asdict(provision_toolbox(AzureOpenAISettings.from_env())), indent=2))


if __name__ == "__main__":
    main()
