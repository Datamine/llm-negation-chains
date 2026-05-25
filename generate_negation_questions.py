import argparse
import csv
import sys
from pathlib import Path
from typing import Any

import yaml


def load_config(config_path: Path) -> dict[str, Any]:
    with config_path.open(encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)

    if "even_answer" not in config or "odd_answer" not in config:
        raise ValueError("Missing required config field(s): even_answer, odd_answer")  # noqa: TRY003, EM101

    if "negation_counts" not in config and "num_negations" not in config:
        raise ValueError("Config must include either 'negation_counts' or 'num_negations'.")  # noqa: TRY003, EM101

    has_sentence_mode = "sentence" in config or "word_index" in config
    has_template_mode = "question_template" in config or "target_text" in config

    if has_sentence_mode and has_template_mode:
        raise ValueError(
            "Config must use either sentence/word_index mode or question_template/target_text mode, not both.",
        )

    if has_template_mode:
        missing = [field for field in ("question_template", "target_text") if field not in config]
        if missing:
            raise ValueError(f"Missing required config field(s): {', '.join(missing)}")  # noqa: TRY003, EM102
    else:
        missing = [field for field in ("sentence", "word_index") if field not in config]
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


def resolve_negation_counts(config: dict[str, Any]) -> list[int]:
    if "negation_counts" in config:
        raw_counts = config["negation_counts"]
        if not isinstance(raw_counts, list) or not raw_counts:
            raise ValueError("'negation_counts' must be a non-empty list when provided.")  # noqa: TRY003, EM101
        counts = [int(count) for count in raw_counts]
    else:
        num_negations = int(config["num_negations"])
        if num_negations < 0:
            raise ValueError("'num_negations' must be zero or greater.")  # noqa: TRY003, EM101
        counts = list(range(num_negations + 1))

    if any(count < 0 for count in counts):
        raise ValueError("All negation counts must be zero or greater.")  # noqa: TRY003, EM101

    ordered_unique_counts = list(dict.fromkeys(counts))
    return ordered_unique_counts


def generate_template_question(
    *,
    template: str,
    target_text: str,
    negation_count: int,
    negation_token: str,
) -> str:
    negation_phrase = " ".join([negation_token] * negation_count).strip()
    chain_text = " ".join(part for part in (negation_phrase, target_text) if part).strip()
    parity = "even" if negation_count % 2 == 0 else "odd"
    return template.format(
        negation_count=negation_count,
        negation_phrase=negation_phrase,
        target_text=target_text,
        chain_text=chain_text,
        parity=parity,
    )


def generate_rows(config: dict[str, Any]) -> list[dict[str, str]]:
    even_answer = str(config["even_answer"]).strip()
    odd_answer = str(config["odd_answer"]).strip()
    if not even_answer or not odd_answer:
        raise ValueError("'even_answer' and 'odd_answer' must not be empty.")  # noqa: TRY003, EM101

    negation_counts = resolve_negation_counts(config)

    rows = []
    if "question_template" in config:
        template = str(config["question_template"]).strip()
        target_text = str(config["target_text"]).strip()
        negation_token = str(config.get("negation_token", "not")).strip()
        if not template or not target_text or not negation_token:
            raise ValueError(
                "'question_template', 'target_text', and 'negation_token' must not be empty.",
            )  # noqa: TRY003, EM101
    else:
        sentence = str(config["sentence"]).strip()
        words = sentence.split()
        if not words:
            raise ValueError("'sentence' must not be empty.")  # noqa: TRY003, EM101
        insert_index = resolve_insert_index(int(config["word_index"]), len(words))

    for negation_count in negation_counts:
        parity = "even" if negation_count % 2 == 0 else "odd"
        if "question_template" in config:
            question = generate_template_question(
                template=template,
                target_text=target_text,
                negation_count=negation_count,
                negation_token=negation_token,
            )
        else:
            question = generate_question(sentence, insert_index, negation_count)
        rows.append(
            {
                "Question": question,
                "NegationCount": str(negation_count),
                "ExpectedAnswer": even_answer if parity == "even" else odd_answer,
            },
        )
    return rows


def write_rows(output_path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = ["NegationCount", "ExpectedAnswer", "Question"]
    output_path.parent.mkdir(parents=True, exist_ok=True)
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
        default="ExperimentConfigs/legacy/default_questions.yaml",
        help="Path to the question config YAML file. Defaults to ExperimentConfigs/legacy/default_questions.yaml.",
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
