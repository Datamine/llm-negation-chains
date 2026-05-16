import argparse
import csv
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from llm_interface import OpenRouterClient

BOOLEAN_ANSWERS = {"yes", "no", "true", "false"}
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0
REDIS_PASSWORD = None
REDIS_PASSWORD_ENV = "REDIS_PASSWORD"
REQUEST_TIMEOUT_SECONDS = 120


@dataclass
class RedisCacheConfig:
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: str | None = None
    password_env: str | None = None


class RedisResultCache:
    def __init__(self, config: RedisCacheConfig) -> None:
        self.config = config
        try:
            import redis
        except ImportError as exc:  # pragma: no cover - depends on local environment
            raise RuntimeError(
                "Redis caching was requested, but the 'redis' package is not installed.",
            ) from exc

        password = config.password
        if password is None and config.password_env:
            password = os.environ.get(config.password_env)

        self.client = redis.Redis(  # type: ignore[no-untyped-call]
            host=config.host,
            port=config.port,
            db=config.db,
            password=password,
            decode_responses=True,
        )

    def _key(self, model: str, question: str) -> str:
        digest = hashlib.sha256(question.encode("utf-8")).hexdigest()
        return f"answers:{model}:{digest}"

    def get_answers(self, model: str, question: str) -> list[dict[str, Any]]:
        stored_entries = self.client.lrange(self._key(model, question), 0, -1)
        return [json.loads(entry) for entry in stored_entries]

    def append_answer(self, model: str, question: str, entry: dict[str, Any]) -> None:
        self.client.rpush(self._key(model, question), json.dumps(entry))


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
        if not reader.fieldnames or "Question" not in reader.fieldnames:
            raise ValueError("Questions CSV must contain a 'Question' column.")  # noqa: TRY003, EM101

        rows = [row for row in reader if (row.get("Question") or "").strip()]
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

    raise ValueError(
        "Model response did not contain a recognizable boolean answer: "
        f"{raw_response!r}",
    )


def build_clients(config: dict[str, Any]) -> list[OpenRouterClient]:
    rate_limit_seconds = int(config.get("rate_limit_between_calls_seconds", 0))
    measure_performance = bool(config.get("measure_performance", False))

    return [
        OpenRouterClient(
            model=model_name,
            rate_limit_between_calls=rate_limit_seconds,
            timeout_seconds=REQUEST_TIMEOUT_SECONDS,
            measure_performance=measure_performance,
        )
        for model_name in config["models"]
    ]


def build_cache(config: dict[str, Any]) -> RedisResultCache | None:
    if not config.get("use_redis_cache", False):
        return None

    cache_config = RedisCacheConfig(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        password=REDIS_PASSWORD,
        password_env=REDIS_PASSWORD_ENV,
    )
    return RedisResultCache(cache_config)


def fetch_answers_for_question(
    client: OpenRouterClient,
    question: str,
    runs_per_question: int,
    cache: RedisResultCache | None,
) -> list[dict[str, Any]]:
    cached_entries: list[dict[str, Any]] = []
    if cache is not None:
        cached_entries = cache.get_answers(client.model_name, question)

    answers = cached_entries[:runs_per_question]
    missing_runs = runs_per_question - len(answers)

    for _ in range(missing_runs):
        raw_response = client.call_model(question)
        answer = normalize_answer(raw_response)
        live_entry = {
            "answer": answer,
            "raw_response": raw_response,
            "source": "live",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }
        answers.append(live_entry)
        if cache is not None:
            cache.append_answer(client.model_name, question, live_entry)

    for entry in answers[: len(cached_entries[:runs_per_question])]:
        entry["source"] = "redis_cache"

    return answers


def default_output_path(config_path: Path) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return config_path.with_name(f"{config_path.stem}_{timestamp}_results.csv")


def run(config_path: Path) -> Path:
    config = load_run_config(config_path)
    questions_path = Path(config["questions_csv"])
    if not questions_path.is_absolute():
        questions_path = config_path.parent / questions_path

    output_path = Path(config.get("output_csv") or default_output_path(config_path))
    if not output_path.is_absolute():
        output_path = config_path.parent / output_path

    question_rows, question_columns = load_questions(questions_path)
    clients = build_clients(config)
    cache = build_cache(config)
    serialized_config = json.dumps(config, sort_keys=True)

    output_columns = [
        *question_columns,
        "model",
        "run_index",
        "answer",
        "raw_response",
        "response_source",
    ]

    with output_path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.writer(output_file)
        writer.writerow([serialized_config])
        writer.writerow(output_columns)

        for row in question_rows:
            question = row["Question"]
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
        default="config_run.json",
        help="Path to the run config JSON file. Defaults to config_run.json.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_path = run(Path(args.config).resolve())
    print(output_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
