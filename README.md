# llm-negation-chains

This is an experiment for how well LLMs handle chains of negations. For example, "not not not False" should evaluate to True. A very long negation chain might be evaluated incorrectly by an LLM due to its attention length.

This repository contains a simple harness to statistically test how well OpenRouter-backed LLMs handle negations of a given chain length.

Generated question sheets live under `Questions/`. Harness result CSVs live under `Answers/`.

## Generate Questions

Edit `config_questions.yaml`, then run:

```bash
python3 generate_negation_questions.py config_questions.yaml
```

This writes a CSV under `Questions/` with `NegationCount`, `ExpectedAnswer`, and `Question` columns.

`word_index` is indexed from zero. It is the token position before which `not` should be inserted, so the example value `7` inserts `not` before `allowed`.

`num_negations` controls the largest negation count generated. If it is `8`, the CSV contains variants for `0` through `8` inserted `not` tokens.

`even_answer` and `odd_answer` define the expected label for each parity class, for example `yes` / `no` or `true` / `false`.

## Run The Harness

Edit `config_answers.yaml`, then run:

```bash
python3 generate_answers_from_questions.py config_answers.yaml
```

The harness:

- reads models from OpenRouter
- loads questions from the CSV's `Question` and `ExpectedAnswer` columns
- runs each model `runs_per_question` times per question
- parallelizes across models with an optional `max_workers` value in `config_answers.yaml`
- accepts an optional `max_tokens` value in `config_answers.yaml`
- optionally reuses Redis-cached answers and only calls the API for missing runs
- uses the Redis connection settings defined in `Utilities/redis_interface.py`
- uses Redis locks so cache population for a given model/question is serialized
- if a model returns HTTP 402 Payment Required, marks the remaining runs for that model as skipped and continues with later models
- keys cached results by model, `max_tokens`, and a hash of the question text
- writes a CSV under `Answers/` named after the question sheet, for example `Questions/questions.csv` -> `Answers/questions-answers.csv`, with cell `A1` containing the serialized run config and the rows below containing one result per question/model/run, including `ExpectedAnswer`, `max_tokens`, `reasoning_tokens`, and a `matches_expected` value of `True`, `False`, or `Inadmissible`

`Inadmissible` means the model did not return an answer in the expected short format. It is recorded in the CSV and counts as not correct rather than being skipped.

## Visualize Results

Generate a line chart of percent correct by negation count:

```bash
python3 helper_plot_accuracy_by_negations.py Answers/questions_parking-answers.csv
```

By default this writes:

```text
Visualizations/questions_parking-answers-accuracy-by-negations.png
```

The chart treats only `matches_expected == True` as correct. Rows marked `False` and `Inadmissible` both stay in the denominator, so inadmissible responses reduce the plotted accuracy rather than being excluded.
