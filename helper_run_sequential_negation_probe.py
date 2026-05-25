import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

from Utilities.llm_interface import GeneralClient
from generate_answers_from_questions import (
    assess_answer,
    extract_reasoning_tokens,
    extract_usage_metric,
    load_questions,
    normalize_answer,
)

DEFAULT_MODELS = [
    "openai/gpt-5.5-pro",
    "anthropic/claude-opus-4.7",
    "moonshotai/kimi-k2.6",
    "google/gemini-3.5-flash",
]
DEFAULT_SYSTEM_PROMPT = (
    "Return only the requested answer token or phrase, in lowercase, "
    "with no punctuation and no explanation."
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run sequential OpenRouter probes for selected negation counts from a question CSV.",
    )
    parser.add_argument("questions_csv", help="Path to the questions CSV.")
    parser.add_argument("output_csv", help="Path to the output answers CSV.")
    parser.add_argument(
        "--counts",
        required=True,
        help="Comma-separated negation counts to run, for example 50,51,100,101.",
    )
    parser.add_argument(
        "--model",
        action="append",
        dest="models",
        help="Model to include. May be repeated. Defaults to the current four-model suite.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=45,
        help="Per-request timeout in seconds. Defaults to 45.",
    )
    parser.add_argument(
        "--reasoning-max-tokens",
        type=int,
        default=65536,
        help="OpenRouter reasoning max_tokens budget. Defaults to 65536.",
    )
    parser.add_argument(
        "--system-prompt",
        default=DEFAULT_SYSTEM_PROMPT,
        help="System prompt to send with each request.",
    )
    return parser.parse_args()


def parse_counts(raw_counts: str) -> list[int]:
    counts = []
    for value in raw_counts.split(","):
        cleaned = value.strip()
        if not cleaned:
            continue
        counts.append(int(cleaned))
    if not counts:
        raise ValueError("At least one negation count is required.")  # noqa: TRY003, EM101
    return counts


def build_clients(args: argparse.Namespace) -> list[GeneralClient]:
    models = args.models or DEFAULT_MODELS
    reasoning: dict[str, Any] = {"max_tokens": int(args.reasoning_max_tokens)}
    return [
        GeneralClient(
            model=model_name,
            timeout_seconds=int(args.timeout_seconds),
            measure_performance=False,
            max_tokens=None,
            system_prompt=str(args.system_prompt),
            reasoning=reasoning,
        )
        for model_name in models
    ]


def main() -> int:
    args = parse_args()
    counts = parse_counts(args.counts)
    questions_path = Path(args.questions_csv).resolve()
    output_path = Path(args.output_csv).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rows, _ = load_questions(questions_path)
    selected_rows = [row for row in rows if int(row["NegationCount"]) in counts]
    selected_counts = {int(row["NegationCount"]) for row in selected_rows}
    missing_counts = [count for count in counts if count not in selected_counts]
    if missing_counts:
        raise ValueError(f"Missing counts in question CSV: {missing_counts}")  # noqa: TRY003, EM102

    clients = build_clients(args)
    serialized_config = json.dumps(
        {
            "models": [client.model_name for client in clients],
            "questions_csv": str(questions_path),
            "targeted_counts": counts,
            "system_prompt": args.system_prompt,
            "reasoning": {"max_tokens": int(args.reasoning_max_tokens)},
            "timeout_seconds": int(args.timeout_seconds),
            "runner": "helper_run_sequential_negation_probe.py",
        },
        sort_keys=True,
    )

    output_columns = [
        "NegationCount",
        "ExpectedAnswer",
        "Question",
        "model",
        "run_index",
        "max_tokens",
        "reasoning_tokens",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "finish_reason",
        "answer",
        "matches_expected",
        "raw_response",
        "response_source",
    ]

    with output_path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.writer(output_file)
        writer.writerow([serialized_config])
        writer.writerow(output_columns)

        for row in selected_rows:
            negation_count = row["NegationCount"]
            expected_answer = row["ExpectedAnswer"]
            question = row["Question"]
            print(f"negation_count={negation_count}")

            for client in clients:
                try:
                    details = client.call_model_details(question)
                    raw_response = details["text"]
                    answer = normalize_answer(raw_response, expected_answer)
                    reasoning_tokens = extract_reasoning_tokens(details.get("usage"))
                    prompt_tokens = extract_usage_metric(details.get("usage"), "prompt_tokens")
                    completion_tokens = extract_usage_metric(details.get("usage"), "completion_tokens")
                    total_tokens = extract_usage_metric(details.get("usage"), "total_tokens")
                    finish_reason = details.get("finish_reason")
                    response_source = "live"
                except Exception as exc:  # noqa: BLE001
                    raw_response = f"{type(exc).__name__}: {exc}"
                    answer = ""
                    reasoning_tokens = ""
                    prompt_tokens = ""
                    completion_tokens = ""
                    total_tokens = ""
                    finish_reason = ""
                    response_source = "request_error"

                writer.writerow(
                    [
                        negation_count,
                        expected_answer,
                        question,
                        client.model_name,
                        1,
                        "",
                        reasoning_tokens,
                        prompt_tokens,
                        completion_tokens,
                        total_tokens,
                        finish_reason,
                        answer,
                        assess_answer(answer, expected_answer),
                        raw_response,
                        response_source,
                    ],
                )
                output_file.flush()
                print(
                    f"  {client.model_name}: "
                    f"answer={answer or 'inadmissible'} "
                    f"source={response_source} "
                    f"reasoning_tokens={reasoning_tokens or 'n/a'}",
                )

    print(output_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
