import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

from Utilities.llm_interface import GeneralClient
from Utilities.redis_interface import RedisAnswerCache

BOOLEAN_ANSWERS = {"yes", "no", "true", "false"}
REQUEST_TIMEOUT_SECONDS = 120


def load_run_config(config_path: Path) -> dict[str, Any]:
    with config_path.open(encoding="utf-8") as config_file:
        config = json.load(config_file)

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


def build_clients(config: dict[str, Any]) -> list[GeneralClient]:
    rate_limit_seconds = int(config.get("rate_limit_between_calls_seconds", 0))
    measure_performance = bool(config.get("measure_performance", False))

    return [
        GeneralClient(
            model=model_name,
            rate_limit_between_calls=rate_limit_seconds,
            timeout_seconds=REQUEST_TIMEOUT_SECONDS,
            measure_performance=measure_performance,
        )
        for model_name in config["models"]
    ]


def build_cache(config: dict[str, Any]) -> RedisAnswerCache | None:
    if not config.get("use_redis_cache", False):
        return None
    return RedisAnswerCache()


def fetch_answers_for_question(
    client: GeneralClient,
    question: str,
    runs_per_question: int,
    cache: RedisAnswerCache | None,
) -> list[dict[str, Any]]:
    def generate_live_entry() -> dict[str, Any]:
        raw_response = client.call_model(question)
        answer = normalize_answer(raw_response)
        return {
            "answer": answer,
            "raw_response": raw_response,
            "source": "live",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }

    cached_count = 0
    if cache is None:
        answers = [generate_live_entry() for _ in range(runs_per_question)]
    else:
        answers, cached_count = cache.ensure_answer_count(
            model=client.model_name,
            question=question,
            desired_count=runs_per_question,
            generate_answer=generate_live_entry,
        )

    for entry in answers[:cached_count]:
        entry["source"] = "redis_cache"

    return answers


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
    cache = build_cache(config)
    serialized_config = json.dumps(config, sort_keys=True)

    output_columns = [
        *question_columns,
        "model",
        "run_index",
        "answer",
        "matches_expected",
        "raw_response",
        "response_source",
    ]

    with output_path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.writer(output_file)
        writer.writerow([serialized_config])
        writer.writerow(output_columns)

        for row in question_rows:
            question = row["Question"]
            expected_answer = row["ExpectedAnswer"]
            for client in clients:
                answers = fetch_answers_for_question(
                    client=client,
                    question=question,
                    runs_per_question=int(config["runs_per_question"]),
                    cache=cache,
                )
                for run_index, entry in enumerate(answers, start=1):
                    output_row = [
                        *[row.get(column, "") for column in question_columns],
                        client.model_name,
                        run_index,
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
        default="config_answers.json",
        help="Path to the answers config JSON file. Defaults to config_answers.json.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_path = run(Path(args.config).resolve())
    print(output_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
