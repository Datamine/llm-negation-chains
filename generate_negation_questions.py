import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any


def load_config(config_path: Path) -> dict[str, Any]:
    with config_path.open(encoding="utf-8") as config_file:
        config = json.load(config_file)

    required_fields = ("sentence", "word_index", "num_negations")
    missing = [field for field in required_fields if field not in config]
    if missing:
        raise ValueError(f"Missing required config field(s): {', '.join(missing)}")  # noqa: TRY003, EM102

    return config


def resolve_insert_index(word_index: int, word_count: int) -> int:
    if word_index < 0 or word_index >= word_count:
        raise ValueError(
            f"word_index resolves to {word_index}, but valid positions are 0 to {word_count - 1}.",
        )
    return word_index


def generate_question(sentence: str, insert_index: int, negation_count: int) -> str:
    words = sentence.split()
    negated_words = words[:insert_index] + (["not"] * negation_count) + words[insert_index:]
    return " ".join(negated_words)


def generate_rows(config: dict[str, Any]) -> list[dict[str, Any]]:
    sentence = str(config["sentence"]).strip()
    words = sentence.split()
    if not words:
        raise ValueError("'sentence' must not be empty.")  # noqa: TRY003, EM101

    num_negations = int(config["num_negations"])
    if num_negations < 0:
        raise ValueError("'num_negations' must be zero or greater.")  # noqa: TRY003, EM101

    insert_index = resolve_insert_index(int(config["word_index"]), len(words))

    rows = []
    for negation_count in range(num_negations + 1):
        rows.append(
            {
                "Question": generate_question(sentence, insert_index, negation_count),
                "NegationCount": negation_count,
                "WordIndex": int(config["word_index"]),
                "InsertBeforeToken": words[insert_index],
                "BaseSentence": sentence,
            },
        )
    return rows


def write_rows(output_path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "Question",
        "NegationCount",
        "WordIndex",
        "InsertBeforeToken",
        "BaseSentence",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a question CSV by inserting repeated negations into a sentence.",
    )
    parser.add_argument(
        "config",
        nargs="?",
        default="config_negations.json",
        help="Path to the negation config JSON file. Defaults to config_negations.json.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config_path = Path(args.config).resolve()
    config = load_config(config_path)
    rows = generate_rows(config)

    output_path = Path(config.get("output_csv", "questions.csv"))
    if not output_path.is_absolute():
        output_path = config_path.parent / output_path

    write_rows(output_path, rows)
    print(output_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
