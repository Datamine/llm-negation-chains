# llm-negation-chains

This is an experiment for how well LLMs handle chains of negations. For example, "not not not False" should evaluate to True. A very long negation chain might be evaluated incorrectly by an LLM due to its attention length.

This repository contains a simple harness to statistically test how well OpenRouter-backed LLMs handle negations of a given chain length.

Generated question sheets live under `Questions/`. Harness result CSVs live under `Answers/`.

## Generate Questions

Edit `config_negations.json`, then run:

```bash
python3 generate_negation_questions.py config_negations.json
```

This writes a CSV under `Questions/` with `Question`, `NegationCount`, `Parity`, and `ExpectedAnswer` columns.

`word_index` is indexed from zero. It is the token position before which `not` should be inserted, so the example value `7` inserts `not` before `allowed`.

`num_negations` controls the largest negation count generated. If it is `8`, the CSV contains variants for `0` through `8` inserted `not` tokens.

`even_answer` and `odd_answer` define the expected label for each parity class, for example `yes` / `no` or `true` / `false`.

## Run The Harness

Edit `config_run.json`, then run:

```bash
python3 run_harness.py config_run.json
```

The harness:

- reads models from OpenRouter
- loads questions from the CSV's `Question` column
- runs each model `runs_per_question` times per question
- optionally reuses Redis-cached answers and only calls the API for missing runs
- uses the Redis connection settings defined in `Utilities/redis_interface.py`
- uses Redis locks so cache population for a given model/question is serialized
- keys cached results by model plus a hash of the question text
- writes a CSV under `Answers/` where cell `A1` contains the serialized run config and the rows below contain one result per question/model/run
