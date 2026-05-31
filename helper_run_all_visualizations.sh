#!/usr/bin/env bash
set -euo pipefail

cd /home/v/negation-chains

python3 helper_generate_suite_visualizations.py

for results_csv in \
  "Answers/boolean_literal_false-answers.csv" \
  "Answers/boolean_literal_true_sequential-answers.csv" \
  "Answers/boolean_counted_false_targeted-answers.csv" \
  "Answers/sentiment_literal_targeted-answers.csv" \
  "Answers/lock_literal_targeted-answers.csv"
do
  python3 helper_plot_accuracy_by_negations.py "$results_csv"
done
