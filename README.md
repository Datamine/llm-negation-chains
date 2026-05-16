# llm-negation-chains

This is an experiment for how well LLMs handle chains of negations. For example, "not not not False" should evaluate to True. A very long negation chain might be evaluated incorrectly by an LLM due to its attention length.

This repository contains a simple harness to statistically test how well OpenRouter-backed LLMs handle negations of a given chain length.

## Generate Questions

Edit `config_negations.json` or create your own based on `config_negations.example.json`, then run:

```bash
python3 generate_negation_questions.py config_negations.json
```

This writes a CSV with a `Question` column plus metadata columns such as `NegationCount`.

`word_index` is treated as the token position before which `not` should be inserted. The default indexing is zero-based, so the example value `7` inserts `not` before `allowed`.

## Run The Harness

Edit `config_run.json` or create your own based on `config_run.example.json`, then run:

```bash
python3 run_harness.py config_run.json
```

The harness:

- reads models from OpenRouter
- loads questions from the CSV's `Question` column
- runs each model `runs_per_question` times per question
- optionally reuses Redis-cached answers and only calls the API for missing runs
- uses the Redis connection settings and request timeout defined at the top of `run_harness.py`
- keys cached results by model plus a hash of the question text
- writes a CSV where cell `A1` contains the serialized run config and the rows below contain one result per question/model/run
