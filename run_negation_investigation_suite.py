import argparse
import subprocess
import sys
from pathlib import Path


QUESTION_CONFIGS = [
    "ExperimentConfigs/questions_boolean_literal_false.yaml",
    "ExperimentConfigs/questions_boolean_literal_true.yaml",
    "ExperimentConfigs/questions_boolean_counted_false.yaml",
    "ExperimentConfigs/questions_boolean_literal_false_annotated.yaml",
    "ExperimentConfigs/questions_parking_literal.yaml",
]

ANSWER_CONFIGS = [
    "ExperimentConfigs/answers_boolean_literal_false.yaml",
    "ExperimentConfigs/answers_boolean_literal_true.yaml",
    "ExperimentConfigs/answers_boolean_counted_false.yaml",
    "ExperimentConfigs/answers_boolean_literal_false_annotated.yaml",
    "ExperimentConfigs/answers_parking_literal.yaml",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate question sheets and run the configured negation investigation suite.",
    )
    parser.add_argument(
        "--generate-only",
        action="store_true",
        help="Only generate the question CSVs.",
    )
    parser.add_argument(
        "--answers-only",
        action="store_true",
        help="Skip question generation and only run the answer harness.",
    )
    return parser.parse_args()


def run_command(*args: str) -> None:
    subprocess.run([sys.executable, *args], check=True)


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parent

    if not args.answers_only:
        for config in QUESTION_CONFIGS:
            run_command(str(root / "generate_negation_questions.py"), str(root / config))

    if not args.generate_only:
        for config in ANSWER_CONFIGS:
            run_command(str(root / "generate_answers_from_questions.py"), str(root / config))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
