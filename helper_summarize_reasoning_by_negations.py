import argparse
import csv
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize accuracy and token-usage trends by negation count from harness CSVs.",
    )
    parser.add_argument(
        "results",
        nargs="+",
        help="One or more answers CSV paths produced by generate_answers_from_questions.py.",
    )
    parser.add_argument(
        "--output-dir",
        default="Reports",
        help="Directory for summary CSV outputs. Defaults to Reports.",
    )
    return parser.parse_args()


def parse_optional_int(value: str) -> int | None:
    cleaned = (value or "").strip()
    if not cleaned:
        return None
    try:
        return int(cleaned)
    except ValueError:
        return None


def safe_mean(values: list[int]) -> float | str:
    if not values:
        return ""
    return round(statistics.fmean(values), 2)


def load_results(path: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as results_file:
        raw_reader = csv.reader(results_file)
        config_row = next(raw_reader, [])
        serialized_config = config_row[0] if config_row else ""
        config = json.loads(serialized_config) if serialized_config else {}
        header_row = next(raw_reader, [])
        reader = csv.DictReader(results_file, fieldnames=header_row)
        rows = list(reader)
    return config, rows


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    summary_rows: list[dict[str, Any]] = []
    by_negation_rows: list[dict[str, Any]] = []

    for result in args.results:
        path = Path(result).resolve()
        config, rows = load_results(path)
        dataset_name = path.stem
        print(f"\n== {dataset_name} ==")

        grouped_rows: dict[str, dict[int, list[dict[str, str]]]] = defaultdict(lambda: defaultdict(list))
        for row in rows:
            grouped_rows[row["model"]][int(row["NegationCount"])].append(row)

        for model_name in sorted(grouped_rows):
            counts = grouped_rows[model_name]
            overall_rows = [row for per_count_rows in counts.values() for row in per_count_rows]
            overall_runs = len(overall_rows)
            overall_correct = sum(row["matches_expected"] == "True" for row in overall_rows)
            overall_inadmissible = sum(row["matches_expected"] == "Inadmissible" for row in overall_rows)
            overall_reasoning_tokens = [
                value
                for row in overall_rows
                if (value := parse_optional_int(row.get("reasoning_tokens", ""))) is not None
            ]

            first_nonperfect_count = ""
            max_perfect_count = ""

            for negation_count in sorted(counts):
                per_count_rows = counts[negation_count]
                run_count = len(per_count_rows)
                correct_count = sum(row["matches_expected"] == "True" for row in per_count_rows)
                inadmissible_count = sum(row["matches_expected"] == "Inadmissible" for row in per_count_rows)
                reasoning_tokens = [
                    value
                    for row in per_count_rows
                    if (value := parse_optional_int(row.get("reasoning_tokens", ""))) is not None
                ]
                completion_tokens = [
                    value
                    for row in per_count_rows
                    if (value := parse_optional_int(row.get("completion_tokens", ""))) is not None
                ]
                total_tokens = [
                    value
                    for row in per_count_rows
                    if (value := parse_optional_int(row.get("total_tokens", ""))) is not None
                ]
                accuracy = correct_count / run_count if run_count else 0.0
                inadmissible_rate = inadmissible_count / run_count if run_count else 0.0

                if accuracy < 1.0 and first_nonperfect_count == "":
                    first_nonperfect_count = negation_count
                if accuracy == 1.0:
                    max_perfect_count = negation_count

                by_negation_rows.append(
                    {
                        "dataset": dataset_name,
                        "results_path": str(path),
                        "model": model_name,
                        "negation_count": negation_count,
                        "runs": run_count,
                        "accuracy": round(accuracy, 4),
                        "inadmissible_rate": round(inadmissible_rate, 4),
                        "mean_reasoning_tokens": safe_mean(reasoning_tokens),
                        "mean_completion_tokens": safe_mean(completion_tokens),
                        "mean_total_tokens": safe_mean(total_tokens),
                    },
                )

            accuracy_percent = 100.0 * overall_correct / overall_runs if overall_runs else 0.0
            inadmissible_percent = 100.0 * overall_inadmissible / overall_runs if overall_runs else 0.0
            summary_rows.append(
                {
                    "dataset": dataset_name,
                    "results_path": str(path),
                    "model": model_name,
                    "questions_csv": config.get("questions_csv", ""),
                    "runs_per_question": config.get("runs_per_question", ""),
                    "reasoning": json.dumps(config.get("reasoning", {}), sort_keys=True),
                    "system_prompt": config.get("system_prompt", ""),
                    "runs": overall_runs,
                    "accuracy_percent": round(accuracy_percent, 2),
                    "inadmissible_percent": round(inadmissible_percent, 2),
                    "mean_reasoning_tokens": safe_mean(overall_reasoning_tokens),
                    "first_nonperfect_negation_count": first_nonperfect_count,
                    "max_perfect_negation_count": max_perfect_count,
                },
            )

            print(
                f"{model_name}: accuracy={accuracy_percent:.1f}% "
                f"inadmissible={inadmissible_percent:.1f}% "
                f"mean_reasoning_tokens={safe_mean(overall_reasoning_tokens) or 'n/a'} "
                f"first_nonperfect={first_nonperfect_count or 'none'} "
                f"max_perfect={max_perfect_count or 'none'}",
            )

    summary_path = output_dir / "negation_suite_summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8") as summary_file:
        writer = csv.DictWriter(
            summary_file,
            fieldnames=[
                "dataset",
                "results_path",
                "model",
                "questions_csv",
                "runs_per_question",
                "reasoning",
                "system_prompt",
                "runs",
                "accuracy_percent",
                "inadmissible_percent",
                "mean_reasoning_tokens",
                "first_nonperfect_negation_count",
                "max_perfect_negation_count",
            ],
        )
        writer.writeheader()
        writer.writerows(summary_rows)

    by_negation_path = output_dir / "negation_suite_by_negation.csv"
    with by_negation_path.open("w", newline="", encoding="utf-8") as by_negation_file:
        writer = csv.DictWriter(
            by_negation_file,
            fieldnames=[
                "dataset",
                "results_path",
                "model",
                "negation_count",
                "runs",
                "accuracy",
                "inadmissible_rate",
                "mean_reasoning_tokens",
                "mean_completion_tokens",
                "mean_total_tokens",
            ],
        )
        writer.writeheader()
        writer.writerows(by_negation_rows)

    print(f"\nWrote {summary_path}")
    print(f"Wrote {by_negation_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
