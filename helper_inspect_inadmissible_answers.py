import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from Utilities.redis_interface import get_redis_instance


def load_questions(questions_path: Path) -> list[dict[str, str]]:
    with questions_path.open(newline="", encoding="utf-8") as questions_file:
        reader = csv.DictReader(questions_file)
        if not reader.fieldnames or "Question" not in reader.fieldnames:
            raise ValueError("Questions CSV must contain a 'Question' column.")  # noqa: TRY003, EM101
        return list(reader)


def cache_key(model: str, question: str) -> str:
    digest = hashlib.sha256(question.encode("utf-8")).hexdigest()
    return f"answers:{model}:{digest}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect cached inadmissible answers for a question/model pair.",
    )
    parser.add_argument(
        "--questions",
        default="Questions/questions.csv",
        help="Path to the questions CSV. Defaults to Questions/questions.csv.",
    )
    parser.add_argument(
        "--question-index",
        type=int,
        help="Zero-based question index in the questions CSV. If omitted, scans all questions.",
    )
    parser.add_argument(
        "--model",
        required=True,
        help="Model name used in the Redis cache, for example moonshotai/kimi-k2.6.",
    )
    parser.add_argument(
        "--show-all",
        action="store_true",
        help="Show all cached entries, not just inadmissible ones.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    questions_path = Path(args.questions).resolve()
    rows = load_questions(questions_path)

    redis_instance = get_redis_instance()
    if args.question_index is None:
        question_indexes = range(len(rows))
    else:
        if args.question_index < 0 or args.question_index >= len(rows):
            raise ValueError(
                f"question-index {args.question_index} is out of range for {len(rows)} questions.",
            )
        question_indexes = [args.question_index]

    print(f"Model: {args.model}")
    printed_any = False

    for question_index in question_indexes:
        question_row = rows[question_index]
        question = question_row["Question"]
        key = cache_key(args.model, question)
        entries = redis_instance.lrange(key, 0, -1)

        matching_entries: list[tuple[int, dict[str, Any]]] = []
        for run_index, entry in enumerate(entries, start=1):
            parsed: dict[str, Any] = json.loads(entry)
            answer = parsed.get("answer", "")
            if not args.show_all and answer:
                continue
            matching_entries.append((run_index, parsed))

        if not matching_entries:
            continue

        printed_any = True
        print(f"\nQuestion index: {question_index}")
        print(f"Redis key: {key}")
        print(f"Question: {question}")
        print(f"Cached entries: {len(entries)}")

        for run_index, parsed in matching_entries:
            print(f"\nRun {run_index}")
            print(f"answer: {parsed.get('answer', '')!r}")
            print(f"source: {parsed.get('source')}")
            print(f"timestamp_utc: {parsed.get('timestamp_utc')}")
            print(f"finish_reason: {parsed.get('finish_reason')!r}")
            print(f"usage: {parsed.get('usage')!r}")
            print(f"message: {parsed.get('message')!r}")
            print(f"raw_response: {parsed.get('raw_response')!r}")

    if not printed_any:
        scope = "all questions" if args.question_index is None else f"question {args.question_index}"
        print(f"No matching cached entries found for {args.model} in {scope}.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
