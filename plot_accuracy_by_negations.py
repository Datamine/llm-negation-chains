import argparse
import csv
from collections import defaultdict
from pathlib import Path

try:
    import matplotlib.pyplot as plt
except ImportError as exc:  # pragma: no cover - depends on local environment
    raise RuntimeError(
        "helper_plot_accuracy_by_negations.py requires matplotlib to be installed.",
    ) from exc


def load_results(results_path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with results_path.open(newline="", encoding="utf-8") as results_file:
        reader = csv.reader(results_file)
        next(reader, None)  # config metadata row
        header = next(reader, None)
        if not header:
            raise ValueError("Results CSV is missing a header row.")  # noqa: TRY003, EM101

        required_columns = {"NegationCount", "model", "matches_expected"}
        if not required_columns.issubset(set(header)):
            raise ValueError(
                "Results CSV must contain NegationCount, model, and matches_expected columns.",
            )  # noqa: TRY003, EM101

        rows = [dict(zip(header, row, strict=False)) for row in reader]
        model_order = []
        seen_models = set()
        for row in rows:
            model_name = row["model"]
            if model_name not in seen_models:
                seen_models.add(model_name)
                model_order.append(model_name)
        return rows, model_order


def aggregate_accuracy(rows: list[dict[str, str]]) -> dict[str, dict[int, float]]:
    counts: dict[str, dict[int, dict[str, int]]] = defaultdict(lambda: defaultdict(lambda: {"correct": 0, "total": 0}))

    for row in rows:
        negation_count = int(row["NegationCount"])
        model_name = row["model"]
        counts[model_name][negation_count]["total"] += 1
        if row["matches_expected"] == "True":
            counts[model_name][negation_count]["correct"] += 1

    accuracy: dict[str, dict[int, float]] = {}
    for model_name, by_negation in counts.items():
        accuracy[model_name] = {}
        for negation_count, stats in by_negation.items():
            accuracy[model_name][negation_count] = 100.0 * stats["correct"] / stats["total"]
    return accuracy


def default_output_path(results_path: Path) -> Path:
    return results_path.parent.parent / "Visualizations" / f"{results_path.stem}-accuracy-by-negations.png"


def plot_accuracy(
    accuracy: dict[str, dict[int, float]],
    model_order: list[str],
    output_path: Path,
    title: str,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    plt.figure(figsize=(10, 6))
    for model_name in model_order:
        if model_name not in accuracy:
            continue
        x_values = sorted(accuracy[model_name])
        y_values = [accuracy[model_name][negation_count] for negation_count in x_values]
        plt.plot(x_values, y_values, marker="o", linewidth=2, label=model_name)

    plt.xlabel("Number of Negations")
    plt.ylabel("% Correct")
    plt.ylim(0, 100)
    plt.title(title)
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    plt.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot model accuracy against negation count from an answers CSV.",
    )
    parser.add_argument(
        "results",
        help="Path to the answers CSV, for example Answers/questions_parking-answers.csv.",
    )
    parser.add_argument(
        "--output",
        help="Optional output image path. Defaults to Visualizations/<results-stem>-accuracy-by-negations.png.",
    )
    parser.add_argument(
        "--title",
        default="Accuracy by Negation Count",
        help="Chart title.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    results_path = Path(args.results).resolve()
    rows, model_order = load_results(results_path)
    accuracy = aggregate_accuracy(rows)

    output_path = Path(args.output).resolve() if args.output else default_output_path(results_path)
    plot_accuracy(
        accuracy=accuracy,
        model_order=model_order,
        output_path=output_path,
        title=args.title,
    )
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
