import argparse
import csv
import json
import sys
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from Utilities.llm_interface import GeneralClient, PaymentRequiredError
from Utilities.redis_interface import RedisAnswerCache

BOOLEAN_ANSWERS = {"yes", "no", "true", "false"}
REQUEST_TIMEOUT_SECONDS = 120


def load_run_config(config_path: Path) -> dict[str, Any]:
    with config_path.open(encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)

    required_fields = ("models", "questions_csv", "runs_per_question")
    missing = [field for field in required_fields if field not in config]
    if missing:
        raise ValueError(f"Missing required config field(s): {', '.join(missing)}")  # noqa: TRY003, EM102

    if not isinstance(config["models"], list) or not config["models"]:
        raise ValueError("'models' must be a non-empty list.")  # noqa: TRY003, EM101

    if int(config["runs_per_question"]) <= 0:
        raise ValueError("'runs_per_question' must be a positive integer.")  # noqa: TRY003, EM101

    return config


def load_questions(questions_path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with questions_path.open(newline="", encoding="utf-8") as questions_file:
        reader = csv.DictReader(questions_file)
        if not reader.fieldnames or "Question" not in reader.fieldnames or "ExpectedAnswer" not in reader.fieldnames:
            raise ValueError(
                "Questions CSV must contain 'Question' and 'ExpectedAnswer' columns.",
            )  # noqa: TRY003, EM101

        rows = [row for row in reader if (row.get("Question") or "").strip()]
        for row in rows:
            if not (row.get("ExpectedAnswer") or "").strip():
                raise ValueError("Each question row must include a non-empty 'ExpectedAnswer'.")  # noqa: TRY003, EM101
        return rows, list(reader.fieldnames)


def normalize_answer(raw_response: str) -> str:
    cleaned = raw_response.strip().lower()
    tokens = []
    current_token = []

    for character in cleaned:
        if character.isalpha():
            current_token.append(character)
            continue
        if current_token:
            tokens.append("".join(current_token))
            current_token = []

    if current_token:
        tokens.append("".join(current_token))

    for token in tokens:
        if token in BOOLEAN_ANSWERS:
            return token
    return ""


def assess_answer(answer: str, expected_answer: str) -> str:
    if not answer:
        return "Inadmissible"
    return str(answer.strip().lower() == expected_answer.strip().lower())


def extract_reasoning_tokens(usage: Any) -> int | str:
    if not isinstance(usage, dict):
        return ""
    completion_details = usage.get("completion_tokens_details")
    if not isinstance(completion_details, dict):
        return ""
    reasoning_tokens = completion_details.get("reasoning_tokens")
    return reasoning_tokens if isinstance(reasoning_tokens, int) else ""


def build_clients(config: dict[str, Any]) -> list[GeneralClient]:
    measure_performance = bool(config.get("measure_performance", False))
    max_tokens = int(config["max_tokens"]) if "max_tokens" in config else None

    return [
        GeneralClient(
            model=model_name,
            timeout_seconds=REQUEST_TIMEOUT_SECONDS,
            measure_performance=measure_performance,
            max_tokens=max_tokens,
        )
        for model_name in config["models"]
    ]


def resolve_max_workers(config: dict[str, Any], client_count: int) -> int:
    configured = int(config.get("max_workers", min(4, client_count)))
    return max(1, configured)


def build_cache(config: dict[str, Any]) -> RedisAnswerCache | None:
    if not config.get("use_redis_cache", False):
        return None
    return RedisAnswerCache()


def fetch_answers_for_question(
    client: GeneralClient,
    question: str,
    runs_per_question: int,
    cache: RedisAnswerCache | None,
) -> tuple[list[dict[str, Any]], bool]:
    def generate_live_entry() -> dict[str, Any]:
        details = client.call_model_details(question)
        raw_response = details["text"]
        answer = normalize_answer(raw_response)
        return {
            "answer": answer,
            "max_tokens": client.max_tokens,
            "reasoning_tokens": extract_reasoning_tokens(details.get("usage")),
            "raw_response": raw_response,
            "finish_reason": details.get("finish_reason"),
            "usage": details.get("usage"),
            "message": details.get("message"),
            "source": "live",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }

    cached_count = 0
    payment_required = False
    if cache is None:
        answers = []
        for _ in range(runs_per_question):
            try:
                answers.append(generate_live_entry())
            except PaymentRequiredError:
                payment_required = True
                break
    else:
        answers, cached_count, payment_required = cache.ensure_answer_count(
            model=client.model_name,
            question=question,
            max_tokens=client.max_tokens,
            desired_count=runs_per_question,
            generate_answer=generate_live_entry,
        )

    for entry in answers[:cached_count]:
        entry["source"] = "redis_cache"

    return answers, payment_required


def skipped_entries(runs_per_question: int, reason: str) -> list[dict[str, str]]:
    return [
        {
            "answer": "",
            "max_tokens": "",
            "reasoning_tokens": "",
            "raw_response": reason,
            "source": "payment_required_skip",
            "timestamp_utc": "",
        }
        for _ in range(runs_per_question)
    ]


def process_client_for_question(
    client: GeneralClient,
    question: str,
    runs_per_question: int,
    cache: RedisAnswerCache | None,
) -> tuple[str, list[dict[str, Any]], bool]:
    answers, payment_required = fetch_answers_for_question(
        client=client,
        question=question,
        runs_per_question=runs_per_question,
        cache=cache,
    )
    return client.model_name, answers, payment_required


def print_progress(
    *,
    model_name: str,
    question_index: int,
    total_questions: int,
    run_index: int,
    runs_per_question: int,
    source: str,
    answer: str,
) -> None:
    print(
        f"[{model_name}] question {question_index}/{total_questions} "
        f"run {run_index}/{runs_per_question} "
        f"source={source} answer={answer or 'inadmissible'}",
    )


def default_output_path(config_path: Path, questions_path: Path) -> Path:
    return config_path.parent / "Answers" / f"{questions_path.stem}-answers.csv"


def run(config_path: Path) -> Path:
    config = load_run_config(config_path)
    questions_path = Path(config["questions_csv"])
    if not questions_path.is_absolute():
        questions_path = config_path.parent / questions_path

    output_path = Path(config.get("output_csv") or default_output_path(config_path, questions_path))
    if not output_path.is_absolute():
        output_path = config_path.parent / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)

    question_rows, question_columns = load_questions(questions_path)
    clients = build_clients(config)
    max_workers = resolve_max_workers(config, len(clients))
    cache = build_cache(config)
    serialized_config = json.dumps(config, sort_keys=True)
    skipped_models: set[str] = set()

    output_columns = [
        *question_columns,
        "model",
        "run_index",
        "max_tokens",
        "reasoning_tokens",
        "answer",
        "matches_expected",
        "raw_response",
        "response_source",
    ]

    with output_path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.writer(output_file)
        writer.writerow([serialized_config])
        writer.writerow(output_columns)

        total_questions = len(question_rows)
        runs_per_question = int(config["runs_per_question"])
        print(f"Using up to {max_workers} worker threads across models.")
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for question_index, row in enumerate(question_rows, start=1):
                question = row["Question"]
                expected_answer = row["ExpectedAnswer"]
                futures_by_model: dict[str, Future[tuple[str, list[dict[str, Any]], bool]]] = {}

                for client in clients:
                    if client.model_name in skipped_models:
                        continue
                    print(
                        f"[{client.model_name}] starting question "
                        f"{question_index}/{total_questions}",
                    )
                    futures_by_model[client.model_name] = executor.submit(
                        process_client_for_question,
                        client,
                        question,
                        runs_per_question,
                        cache,
                    )

                for client in clients:
                    if client.model_name in skipped_models:
                        answers = skipped_entries(
                            runs_per_question=runs_per_question,
                            reason="Skipped after earlier HTTP 402 Payment Required.",
                        )
                    else:
                        _, answers, payment_required = futures_by_model[client.model_name].result()
                        if payment_required:
                            skipped_models.add(client.model_name)
                            print(
                                f"[{client.model_name}] HTTP 402 Payment Required; "
                                "skipping remaining runs for this model.",
                            )
                            answers.extend(
                                skipped_entries(
                                    runs_per_question=runs_per_question - len(answers),
                                    reason="Skipped after HTTP 402 Payment Required.",
                                ),
                            )
                    for run_index, entry in enumerate(answers, start=1):
                        print_progress(
                            model_name=client.model_name,
                            question_index=question_index,
                            total_questions=total_questions,
                            run_index=run_index,
                            runs_per_question=runs_per_question,
                            source=entry["source"],
                            answer=entry["answer"],
                        )
                        output_row = [
                            *[row.get(column, "") for column in question_columns],
                            client.model_name,
                            run_index,
                            entry.get("max_tokens", ""),
                            entry.get("reasoning_tokens", ""),
                            entry["answer"],
                            assess_answer(entry["answer"], expected_answer),
                            entry["raw_response"],
                            entry["source"],
                        ]
                        writer.writerow(output_row)

    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a set of OpenRouter models against a question CSV.",
    )
    parser.add_argument(
        "config",
        nargs="?",
        default="config_answers.yaml",
        help="Path to the answers config YAML file. Defaults to config_answers.yaml.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_path = run(Path(args.config).resolve())
    print(output_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
