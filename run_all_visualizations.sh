#!/usr/bin/env bash
set -euo pipefail

cd /home/v/negation-chains

python3 generate_suite_visualizations.py

for results_csv in \
  "Answers/investigation_boolean_literal_false-answers.csv" \
  "Answers/investigation_boolean_literal_true_sequential-answers.csv" \
  "Answers/investigation_boolean_counted_false_targeted-answers.csv" \
  "Answers/investigation_sentiment_literal_targeted-answers.csv" \
  "Answers/investigation_lock_literal_targeted-answers.csv"
do
  python3 plot_accuracy_by_negations.py "$results_csv"
done
