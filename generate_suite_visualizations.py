import csv
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

try:
    import matplotlib.pyplot as plt
except ImportError as exc:  # pragma: no cover - depends on local environment
    raise RuntimeError("generate_suite_visualizations.py requires matplotlib to be installed.") from exc


MODEL_LABELS = {
    "openai/gpt-5.5-pro": "GPT-5.5-Pro",
    "anthropic/claude-opus-4.7": "Claude Opus 4.7",
    "moonshotai/kimi-k2.6": "Kimi K2.6",
    "google/gemini-3.5-flash": "Gemini 3.5 Flash",
}

MODEL_COLORS = {
    "openai/gpt-5.5-pro": "#0b3c5d",
    "anthropic/claude-opus-4.7": "#b33f62",
    "moonshotai/kimi-k2.6": "#f18f01",
    "google/gemini-3.5-flash": "#2a9d8f",
}

DATASET_LABELS = {
    "investigation_boolean_literal_false-answers": "Boolean Literal False Base",
    "investigation_boolean_literal_true_sequential-answers": "Boolean Literal True Base",
    "investigation_boolean_counted_false_targeted-answers": "Boolean Counted False Base",
    "investigation_sentiment_literal_targeted-answers": "Sentiment Literal",
    "investigation_lock_literal_targeted-answers": "Lock State Literal",
}

DATASET_ORDER = [
    "investigation_boolean_literal_false-answers",
    "investigation_boolean_literal_true_sequential-answers",
    "investigation_boolean_counted_false_targeted-answers",
    "investigation_sentiment_literal_targeted-answers",
    "investigation_lock_literal_targeted-answers",
]


def parse_optional_float(value: str) -> float | None:
    cleaned = (value or "").strip()
    if not cleaned:
        return None
    return float(cleaned)


def load_answers_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as results_file:
        reader = csv.reader(results_file)
        next(reader, None)
        header = next(reader, None)
        if not header:
            raise ValueError(f"Missing header row in {path}")  # noqa: TRY003, EM102
        return [dict(zip(header, row, strict=False)) for row in reader]


def load_by_negation_report(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as report_file:
        return list(csv.DictReader(report_file))


def aggregate_accuracy(rows: list[dict[str, str]]) -> dict[str, dict[int, float]]:
    grouped: dict[str, dict[int, dict[str, int]]] = defaultdict(lambda: defaultdict(lambda: {"correct": 0, "total": 0}))
    for row in rows:
        model_name = row["model"]
        negation_count = int(row["NegationCount"])
        grouped[model_name][negation_count]["total"] += 1
        if row["matches_expected"] == "True":
            grouped[model_name][negation_count]["correct"] += 1

    accuracy: dict[str, dict[int, float]] = {}
    for model_name, per_count in grouped.items():
        accuracy[model_name] = {}
        for negation_count, stats in per_count.items():
            accuracy[model_name][negation_count] = 100.0 * stats["correct"] / stats["total"]
    return accuracy


def aggregate_reasoning_tokens(rows: list[dict[str, str]]) -> dict[str, dict[int, float]]:
    grouped: dict[str, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        maybe_value = parse_optional_float(row.get("reasoning_tokens", ""))
        if maybe_value is None:
            continue
        grouped[row["model"]][int(row["NegationCount"])].append(maybe_value)

    aggregated: dict[str, dict[int, float]] = {}
    for model_name, per_count in grouped.items():
        aggregated[model_name] = {}
        for negation_count, values in per_count.items():
            aggregated[model_name][negation_count] = sum(values) / len(values)
    return aggregated


def plot_dataset_panels(
    *,
    output_path: Path,
    datasets: list[tuple[str, dict[str, dict[int, float]]]],
    ylabel: str,
    title: str,
    log_y: bool = False,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure, axes = plt.subplots(3, 2, figsize=(14, 12))
    flat_axes = list(axes.flatten())

    for axis in flat_axes[len(datasets):]:
        axis.axis("off")

    for axis, (dataset_name, values_by_model) in zip(flat_axes, datasets, strict=False):
        counts = sorted({count for per_model in values_by_model.values() for count in per_model})
        x_positions = list(range(len(counts)))

        for model_name in MODEL_LABELS:
            per_model = values_by_model.get(model_name)
            if not per_model:
                continue
            y_values = [per_model.get(count, math.nan) for count in counts]
            axis.plot(
                x_positions,
                y_values,
                marker="o",
                linewidth=2,
                markersize=5,
                label=MODEL_LABELS[model_name],
                color=MODEL_COLORS[model_name],
            )

        axis.set_title(DATASET_LABELS.get(dataset_name, dataset_name), fontsize=11, pad=10)
        axis.set_xticks(x_positions)
        axis.set_xticklabels([str(count) for count in counts], rotation=45, ha="right")
        axis.set_ylabel(ylabel)
        axis.grid(True, alpha=0.25)
        if log_y:
            axis.set_yscale("log")
        elif ylabel.startswith("Accuracy"):
            axis.set_ylim(-2, 102)

    handles, labels = flat_axes[0].get_legend_handles_labels()
    if handles:
        figure.legend(handles, labels, loc="upper center", ncol=2, frameon=False)
    figure.suptitle(title, fontsize=15, y=0.98)
    figure.tight_layout(rect=(0, 0, 1, 0.95))
    figure.savefig(output_path, dpi=220)
    plt.close(figure)


def plot_boolean_priming_comparison(
    *,
    false_rows: list[dict[str, str]],
    true_rows: list[dict[str, str]],
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    false_accuracy = aggregate_accuracy(false_rows)
    true_accuracy = aggregate_accuracy(true_rows)
    false_reasoning = aggregate_reasoning_tokens(false_rows)
    true_reasoning = aggregate_reasoning_tokens(true_rows)

    overlap_counts = sorted(
        {int(row["NegationCount"]) for row in false_rows}.intersection(
            {int(row["NegationCount"]) for row in true_rows},
        ),
    )
    x_positions = list(range(len(overlap_counts)))

    figure, axes = plt.subplots(2, 2, figsize=(15, 10))
    panels = [
        (axes[0][0], false_accuracy, "False Base Accuracy", "Accuracy (%)", False),
        (axes[0][1], true_accuracy, "True Base Accuracy", "Accuracy (%)", False),
        (axes[1][0], false_reasoning, "False Base Reasoning Tokens", "Mean reasoning tokens", True),
        (axes[1][1], true_reasoning, "True Base Reasoning Tokens", "Mean reasoning tokens", True),
    ]

    for axis, values_by_model, panel_title, ylabel, log_y in panels:
        for model_name in MODEL_LABELS:
            per_model = values_by_model.get(model_name, {})
            y_values = [per_model.get(count, math.nan) for count in overlap_counts]
            axis.plot(
                x_positions,
                y_values,
                marker="o",
                linewidth=2,
                markersize=5,
                label=MODEL_LABELS[model_name],
                color=MODEL_COLORS[model_name],
            )
        axis.set_title(panel_title, fontsize=11, pad=10)
        axis.set_xticks(x_positions)
        axis.set_xticklabels([str(count) for count in overlap_counts], rotation=45, ha="right")
        axis.set_ylabel(ylabel)
        axis.grid(True, alpha=0.25)
        if log_y:
            axis.set_yscale("log")
        else:
            axis.set_ylim(-2, 102)

    handles, labels = axes[0][0].get_legend_handles_labels()
    figure.legend(handles, labels, loc="upper center", ncol=2, frameon=False)
    figure.suptitle("Boolean Priming Comparison: False Base vs True Base", fontsize=15, y=0.98)
    figure.tight_layout(rect=(0, 0, 1, 0.95))
    figure.savefig(output_path, dpi=220)
    plt.close(figure)


def plot_model_dataset_heatmap(report_rows: list[dict[str, str]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    dataset_names = [name for name in DATASET_ORDER if any(row["dataset"] == name for row in report_rows)]
    model_names = [name for name in MODEL_LABELS if any(row["model"] == name for row in report_rows)]

    matrix = []
    for model_name in model_names:
        row_values = []
        for dataset_name in dataset_names:
            matching_row = next(
                (
                    row
                    for row in report_rows
                    if row["dataset"] == dataset_name and row["model"] == model_name
                ),
                None,
            )
            row_values.append(float(matching_row["accuracy_percent"]) if matching_row else math.nan)
        matrix.append(row_values)

    figure, axis = plt.subplots(figsize=(11, 4.5))
    image = axis.imshow(matrix, cmap="YlGnBu", vmin=0, vmax=100, aspect="auto")

    axis.set_xticks(range(len(dataset_names)))
    axis.set_xticklabels([DATASET_LABELS.get(name, name) for name in dataset_names], rotation=25, ha="right")
    axis.set_yticks(range(len(model_names)))
    axis.set_yticklabels([MODEL_LABELS[name] for name in model_names])
    axis.set_title("Accuracy Heatmap Across Completed Investigations")

    for row_index, row_values in enumerate(matrix):
        for column_index, value in enumerate(row_values):
            if math.isnan(value):
                continue
            axis.text(column_index, row_index, f"{value:.1f}", ha="center", va="center", fontsize=9, color="#10212b")

    colorbar = figure.colorbar(image, ax=axis, fraction=0.03, pad=0.04)
    colorbar.set_label("Accuracy (%)")
    figure.tight_layout()
    figure.savefig(output_path, dpi=220)
    plt.close(figure)


def main() -> int:
    answers_dir = Path("Answers").resolve()
    reports_dir = Path("Reports").resolve()
    visualizations_dir = Path("Visualizations").resolve()

    dataset_paths = {
        "investigation_boolean_literal_false-answers": answers_dir / "investigation_boolean_literal_false-answers.csv",
        "investigation_boolean_literal_true_sequential-answers": answers_dir / "investigation_boolean_literal_true_sequential-answers.csv",
        "investigation_boolean_counted_false_targeted-answers": answers_dir / "investigation_boolean_counted_false_targeted-answers.csv",
        "investigation_sentiment_literal_targeted-answers": answers_dir / "investigation_sentiment_literal_targeted-answers.csv",
        "investigation_lock_literal_targeted-answers": answers_dir / "investigation_lock_literal_targeted-answers.csv",
    }

    loaded_rows = {
        dataset_name: load_answers_csv(path)
        for dataset_name, path in dataset_paths.items()
        if path.exists()
    }

    accuracy_panels = [
        (dataset_name, aggregate_accuracy(rows))
        for dataset_name, rows in loaded_rows.items()
    ]
    reasoning_panels = [
        (dataset_name, aggregate_reasoning_tokens(rows))
        for dataset_name, rows in loaded_rows.items()
    ]

    plot_dataset_panels(
        output_path=visualizations_dir / "negation-suite-accuracy-panels.png",
        datasets=accuracy_panels,
        ylabel="Accuracy (%)",
        title="Accuracy Across Negation Investigations",
    )
    plot_dataset_panels(
        output_path=visualizations_dir / "negation-suite-reasoning-token-panels.png",
        datasets=reasoning_panels,
        ylabel="Mean reasoning tokens",
        title="Thinking-Token Growth Across Negation Investigations",
        log_y=True,
    )

    false_rows = loaded_rows.get("investigation_boolean_literal_false-answers")
    true_rows = loaded_rows.get("investigation_boolean_literal_true_sequential-answers")
    if false_rows and true_rows:
        plot_boolean_priming_comparison(
            false_rows=false_rows,
            true_rows=true_rows,
            output_path=visualizations_dir / "negation-suite-boolean-priming-comparison.png",
        )

    report_path = reports_dir / "negation_suite_summary.csv"
    if report_path.exists():
        with report_path.open(newline="", encoding="utf-8") as report_file:
            report_rows = list(csv.DictReader(report_file))
        plot_model_dataset_heatmap(
            report_rows=report_rows,
            output_path=visualizations_dir / "negation-suite-accuracy-heatmap.png",
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
