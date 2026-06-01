# Negation Chain Results

## Overview

This repo contains a set of related negation-chain experiments against four OpenRouter models:

- `openai/gpt-5.5-pro`
- `anthropic/claude-opus-4.7`
- `moonshotai/kimi-k2.6`
- `google/gemini-3.5-flash`

All of the main follow-up runs used a shared OpenRouter reasoning budget of `{"max_tokens": 65536}` so the models were allowed comparable maximum thinking effort. The models still chose very different actual reasoning-token usage.

The most important update from the rerun is that the original `boolean_literal_false` baseline was materially distorted by the old threaded harness. A clean sequential rerun through `100` changes the interpretation a lot:

1. GPT-5.5-Pro is perfect through `100` on the clean `false`-base literal chain.
2. Gemini is also perfect through `100` on that clean rerun.
3. Kimi still has a real literal-chain failure, but it is much narrower than the original threaded baseline suggested.
4. Claude still makes genuine parity / semantic flips even when infrastructure artifacts are removed.
5. Counted prompts remain dramatically easier than literal repeated-token chains.

## Data Files

The main result sets used in this writeup are:

- `Answers/boolean_literal_false_sequential_through_100-answers.csv`
- `Answers/boolean_literal_false-answers.csv`
- `Answers/boolean_counted_false_targeted-answers.csv`
- `Answers/boolean_literal_true_sequential-answers.csv`
- `Answers/sentiment_literal_targeted-answers.csv`
- `Answers/lock_literal_targeted-answers.csv`

Two supplemental files matter for historical context:

- `Answers/boolean_literal_false_targeted_sequential-answers.csv`
- `Questions/boolean_literal_false.csv`

Aggregate summaries are in:

- `Reports/negation_suite_summary.csv`
- `Reports/negation_suite_by_negation.csv`

Visuals are in:

- `Visualizations/negation-suite-accuracy-panels.png`
- `Visualizations/negation-suite-reasoning-token-panels.png`
- `Visualizations/negation-suite-boolean-priming-comparison.png`
- `Visualizations/negation-suite-accuracy-heatmap.png`

## Methodology

### 1. Boolean Literal False Base, Clean Sequential Rerun Through 100

Primary file:

- `Answers/boolean_literal_false_sequential_through_100-answers.csv`

Prompt form:

- literal repeated negation chain ending in `false`
- completed counts: `0..20`, `50`, `51`, `100`

This is now the main reference dataset for the `false`-base literal task. It uses the sequential helper path rather than the original concurrent harness.

Provenance note:

- counts `0..20` and `50` were rerun fresh
- `51` was rerun fresh for GPT and Claude; Kimi and Gemini reused prior sequential-helper rows because the fresh full rerun stalled before those rows completed
- `100` was rerun fresh in isolated subprocesses

So this file is not a single uninterrupted run, but it is still a clean sequential-helper dataset rather than a threaded-harness dataset.

### 2. Boolean Literal False Base, Historical Threaded Baseline

Historical file:

- `Answers/boolean_literal_false-answers.csv`

Prompt form:

- literal repeated negation chain ending in `false`
- counts tested: `0..20`, then `50`, `51`, `100`, `101`, `500`, `501`

This was the original baseline. It ran through the general concurrent answer harness and mixes real reasoning failures with harness artifacts such as timeouts, a malformed-response error, and likely provider-side instability.

It is still useful for historical comparison and for the unresolved very-high-count region, but it should no longer be treated as the primary measurement of `false`-base literal performance.

### 3. Boolean Counted False Base

File:

- `Answers/boolean_counted_false_targeted-answers.csv`

Prompt form:

- asks directly about the result of applying `not` exactly `N` times to `false`
- counts tested: `50`, `51`, `100`, `101`, `500`, `501`, `1000`, `1001`, `10000`, `10001`

This remains the cleanest control condition because it removes the long repeated token chain while preserving the underlying parity task.

### 4. Boolean Literal True Base

File:

- `Answers/boolean_literal_true_sequential-answers.csv`

Prompt form:

- same literal repeated chain, but ending in `true`
- completed counts: `0..20`, `50`, `51`, `100`

This was run sequentially and is the cleanest mirror of the `false`-base task on the overlapping counts.

### 5. Sentiment Literal

File:

- `Answers/sentiment_literal_targeted-answers.csv`

Prompt form:

- "The movie review is not not ... positive. Is the sentiment positive or negative?"
- counts tested: `0`, `1`, `2`, `5`, `10`, `20`, `50`, `51`

### 6. Lock State Literal

File:

- `Answers/lock_literal_targeted-answers.csv`

Prompt form:

- "The vault door is not not ... locked. Is the door locked or unlocked?"
- counts tested: `0`, `1`, `2`, `5`, `10`, `20`, `50`, `51`

## Headline Findings

### A. The original false-base baseline overstated how brittle GPT and Kimi were

On the old threaded baseline:

- GPT-5.5-Pro: `74.07%`
- Claude Opus 4.7: `81.48%`
- Kimi K2.6: `77.78%`
- Gemini 3.5 Flash: `96.3%`

On the clean sequential rerun through `100`:

- GPT-5.5-Pro: `100%`
- Claude Opus 4.7: `83.33%`
- Kimi K2.6: `95.83%`
- Gemini 3.5 Flash: `100%`

On the overlapping completed counts (`0..20`, `50`, `51`, `100`):

- Claude stayed at `20/24`
- Gemini stayed at `24/24`
- Kimi improved from `21/24` to `23/24`
- GPT improved from `20/24` to `24/24`

The clean rerun does not make the task easy for every model, but it does show that the old threaded harness materially exaggerated the weakness of GPT and, to a lesser extent, Kimi.

### B. Literal chains are still harder than counted prompts

The counted control remains much easier:

- GPT-5.5-Pro: `100%`
- Gemini 3.5 Flash: `100%`
- Kimi K2.6: `100%`
- Claude Opus 4.7: `90%`

By contrast, on the clean literal `false`-base rerun through `100`:

- GPT-5.5-Pro: `100%`
- Gemini 3.5 Flash: `100%`
- Kimi K2.6: `95.83%`
- Claude Opus 4.7: `83.33%`

The key point is not that every model collapses on literal chains. It is that the literal repeated-token realization of the problem creates a distinct failure mode that does not appear in the counted prompt.

### C. Claude still shows genuine parity / semantic errors under clean infrastructure

Claude's failures on the clean `false`-base rerun through `100` were:

- wrong at `5`
- wrong at `7`
- wrong at `17`
- wrong at `51`

All four were plain wrong answers, not inadmissibles, and three of them used `0` reported reasoning tokens.

Claude also made clean wrong answers on:

- `boolean_literal_true`: `7`, `10`, `100`
- `sentiment_literal`: `50`
- `lock_literal`: `5`
- `boolean_counted_false`: `1000`

That makes Claude the clearest example of a model that is not just timing out or failing to format, but sometimes confidently flipping the parity result.

### D. Kimi's clean failure profile is narrower than the original baseline implied

On the clean `false`-base rerun through `100`, Kimi has one failure:

- wrong at `51`

That is much cleaner than the old threaded baseline, which had:

- an inadmissible at `8`
- several timeout / request failures at larger counts

So the rerun removes a lot of noise. But Kimi still looks brittle on literal chains:

- wrong at `51` on `boolean_literal_false`
- wrong at `51` on `boolean_literal_true`
- inadmissible at `50` and wrong at `51` on `sentiment_literal`
- wrong at `51` on `lock_literal`

Kimi also tends to spend the most reasoning tokens among the successful literal-chain runs.

### E. On the completed clean tasks, GPT and Gemini are the strongest

Across the cleanly completed tasks in this repo:

- GPT is perfect on `boolean_literal_false` through `100`, `boolean_literal_true` through `100`, `boolean_counted_false`, `sentiment_literal`, and `lock_literal`
- Gemini is also perfect on those completed slices

The remaining uncertainty is at the unresolved very-high-count `false`-base literal tail (`101`, `500`, `501`) because fresh reruns there were blocked by provider stalls and transient DNS failures. Historical sequential data exists for that tail, but it was not fully refreshed in this rerun.

## Per-Dataset Results

### Boolean Literal False Base, Clean Sequential Rerun Through 100

Summary:

- GPT-5.5-Pro: `100%`, `0%` inadmissible
- Claude Opus 4.7: `83.33%`, `0%` inadmissible
- Kimi K2.6: `95.83%`, `0%` inadmissible
- Gemini 3.5 Flash: `100%`, `0%` inadmissible

First non-perfect count:

- Claude: `5`
- Kimi: `51`
- GPT: none through `100`
- Gemini: none through `100`

Notable individual failures:

- Claude: wrong at `5`, `7`, `17`, `51`
- Kimi: wrong at `51`
- GPT: none
- Gemini: none

Interpretation:

- The `false`-base literal task is still not trivial.
- But through `100`, the main clean story is no longer "GPT breaks badly."
- The clean story is now "Claude makes several genuine flips, Kimi has a narrower but real failure point, and GPT / Gemini are stable on the completed range."

### Boolean Literal False Base, Historical Threaded Baseline

Summary:

- GPT-5.5-Pro: `74.07%`, `25.93%` inadmissible
- Claude Opus 4.7: `81.48%`, `7.41%` inadmissible
- Kimi K2.6: `77.78%`, `22.22%` inadmissible
- Gemini 3.5 Flash: `96.3%`, `0%` inadmissible

Historical interpretation:

- This file was important because it first showed that literal chains can be hard.
- It is now best read as a noisy baseline plus historical evidence about the unresolved very-high-count region.
- It should not be used by itself to judge GPT or Kimi on the core `false`-base task.

### Boolean Counted False Base

Summary:

- GPT-5.5-Pro: `100%`
- Gemini 3.5 Flash: `100%`
- Kimi K2.6: `100%`
- Claude Opus 4.7: `90%`

Single failure:

- Claude answered `true` at `1000`, where the correct answer was `false`

Interpretation:

- The parity problem itself is easy for all four models.
- The hard part is the literal repeated textual chain, not the abstract parity mapping.

### Boolean Literal True Base

Summary over completed counts (`0..20`, `50`, `51`, `100`):

- GPT-5.5-Pro: `100%`
- Gemini 3.5 Flash: `100%`
- Kimi K2.6: `95.83%`
- Claude Opus 4.7: `87.5%`

Failures:

- Claude: wrong at `7`, `10`, `100`
- Kimi: wrong at `51`
- GPT: none on the completed counts
- Gemini: none on the completed counts

Interpretation:

- Switching the base from `false` to `true` changes the failure pattern for Claude.
- GPT and Gemini remain stable on the completed overlap.
- Kimi's failure point stays at `51`.

### Sentiment Literal

Summary:

- GPT-5.5-Pro: `100%`
- Gemini 3.5 Flash: `100%`
- Claude Opus 4.7: `87.5%`
- Kimi K2.6: `75%`

Failures:

- Claude: wrong at `50`
- Kimi: inadmissible at `50`, wrong at `51`

Interpretation:

- Wrapping the same negation pattern in a sentiment frame changes model behavior.
- GPT and Gemini stay clean.
- Claude and Kimi remain sensitive to phrasing.

### Lock State Literal

Summary:

- GPT-5.5-Pro: `100%`
- Gemini 3.5 Flash: `100%`
- Claude Opus 4.7: `87.5%`
- Kimi K2.6: `87.5%`

Failures:

- Claude: wrong at `5`
- Kimi: wrong at `51`

Interpretation:

- Framing matters a lot.
- Claude is especially brittle in the lock/unlock phrasing at low counts.

## Priming Effect: False Base vs True Base

The cleanest comparison is now between:

- `Answers/boolean_literal_false_sequential_through_100-answers.csv`
- `Answers/boolean_literal_true_sequential-answers.csv`

Overlap:

- completed overlap: `0..20`, `50`, `51`, `100`
- total overlapping counts per model: `24`

Accuracy on the overlap:

- Claude: `20/24` on `false` base vs `21/24` on `true` base
- Gemini: `24/24` vs `24/24`
- Kimi: `23/24` vs `23/24`
- GPT: `24/24` vs `24/24`

Counts where the classification changed:

- Claude: `5`, `10`, `17`, `51`, `100`
- Gemini: none
- Kimi: none
- GPT: none

Interpretation:

- The strongest remaining priming evidence is now concentrated in Claude.
- The earlier apparent GPT false-vs-true gap was largely a harness-quality artifact.
- Kimi's earlier apparent base-value effect also shrank once the cleaner `false`-base rerun replaced the old threaded baseline.

## Thinking-Token Behavior

### Literal False Base, Clean Sequential Through 100

Mean reasoning tokens:

- GPT: `355.5`
- Claude: `36.83`
- Kimi: `2182.21`
- Gemini: `815.08`

Examples of growth:

- GPT: `147` at `0`, `237` at `20`, `842` at `50`, `2140` at `51`, `2223` at `100`
- Claude: `0` at `0`, `38` at `20`, `66` at `50`, `31` at `51`, `408` at `100`
- Kimi: `305` at `0`, `740` at `20`, `3761` at `50`, `22164` at `51`, `16630` at `100`
- Gemini: `131` at `0`, `749` at `20`, `1849` at `50`, `4800` at `51`, `3207` at `100`

Interpretation:

- Literal chains still induce substantial growth in reasoning-token usage.
- Kimi's token use is especially volatile.
- Claude often commits wrong answers with very little reported reasoning.

### Counted False Base

Mean reasoning tokens:

- GPT: `59.6`
- Claude: `0`
- Kimi: `160.9`
- Gemini: `261.5`

Examples:

- GPT stayed roughly in the `52-71` range even up to `10001`
- Kimi stayed roughly in the `134-225` range
- Gemini stayed roughly in the `208-313` range

Interpretation:

- The counted prompt almost completely removes the thinking-token explosion.
- This is strong evidence that the repeated literal chain itself is the source of the extra effort.

### True Base vs False Base

Mean reasoning tokens:

- GPT: `355.5` on clean literal `false` through `100` vs `407.71` on completed literal `true`
- Claude: `36.83` vs `42.04`
- Kimi: `2182.21` vs `2124.88`
- Gemini: `815.08` vs `643.29`

Interpretation:

- Token usage is highly prompt-path dependent.
- Even when accuracy is unchanged, the model may spend very different internal effort depending on wording and base value.

## Reliability and Caveats

### 1. The clean false-base rerun is now the primary reference

`Answers/boolean_literal_false_sequential_through_100-answers.csv` should be treated as the main `false`-base literal result file.

It is not perfect:

- it is consolidated from multiple sequential-helper outputs
- the `51` rows for Kimi and Gemini come from a prior sequential helper run rather than the fresh rerun

But it is still much cleaner than the historical threaded baseline.

### 2. The very-high-count false-base tail is still unresolved in the fresh rerun

Fresh reruns for `101`, `500`, and `501` were blocked by a mix of:

- stuck provider calls
- transient `Temporary failure in name resolution` request errors

So the clean rerun currently ends at `100`.

Historical evidence for the tail still exists in:

- `Answers/boolean_literal_false-answers.csv`
- `Answers/boolean_literal_false_targeted_sequential-answers.csv`

But that tail was not fully refreshed in this pass.

### 3. The original threaded baseline still contains infrastructure artifacts

`boolean_literal_false-answers.csv` includes:

- timeout-generated inadmissibles
- at least one malformed / partial-response error
- concurrent model execution effects

So it is useful as historical context, not as the primary clean measurement.

### 4. The `true`-base run is partial

The sequential `boolean_literal_true` run completed only through:

- `0..20`
- `50`
- `51`
- `100`

It did not finish `101`, `500`, or `501`.

### 5. The parking follow-up remains partial and is excluded from the main conclusions

There is a partial file:

- `Answers/parking_literal_targeted-answers.csv`

But it stalled and is not clean enough to use as a main headline dataset.

## Overall Interpretation

The current evidence supports the following model:

1. All four models basically understand parity as an abstract rule.
2. Literal repeated negation chains create a separate failure mode that is not captured by counted prompts.
3. The clean rerun shows that the old threaded baseline overstated GPT's and Kimi's weakness on the `false`-base task.
4. Claude still makes genuine parity / semantic flips under clean infrastructure.
5. Kimi remains brittle around the `51` region across multiple literal framings.
6. GPT and Gemini are the strongest on the clean completed task slices in this repo.
7. Prompt framing changes both accuracy and thinking-token usage.
8. The unresolved question is what really happens for all models on a fully refreshed clean rerun of the `101`, `500`, and `501` `false`-base cases.

## Best Current Summary By Model

### GPT-5.5-Pro

- Strongest revision from the rerun
- Perfect on the clean `false`-base rerun through `100`
- Perfect on counted, sentiment, lock, and completed `true`-base data
- The old threaded baseline understated it substantially

### Claude Opus 4.7

- Most clearly prone to real parity flips rather than infrastructure-only failures
- Often uses very low reported reasoning-token counts
- Error locations move with prompt framing and base value

### Kimi K2.6

- Strong on counted prompts
- Better on the clean `false`-base rerun than the old baseline implied
- Still unstable around `51` across several literal task variants
- Often spends extremely large reasoning-token budgets

### Gemini 3.5 Flash

- Tied with GPT on the clean completed task slices
- Very strong literal-chain performance through `100`
- Reasoning-token use grows substantially, but it stays accurate on the completed clean range

## Most Important Next Experiments

If this work continues, the highest-value next steps are:

1. Finish a fully fresh sequential rerun of `boolean_literal_false` at `101`, `500`, and `501`.
2. Run mirrored `true`-base versions of `sentiment_literal` and `lock_literal`.
3. Add more semantic wrappers like permission, temperature, safety, and polarity.
4. Split infrastructure failures from reasoning failures even more aggressively in reporting.
5. Add direct latency measurements next to reasoning-token counts.

## Bottom Line

The main result is no longer just "some models fail long negation chains."

The updated result is:

1. parity reasoning itself is mostly easy
2. literal repeated-token chains create a separate brittle regime
3. the old threaded baseline overstated some failures
4. after cleaning up the infrastructure, Claude still shows genuine parity flips, Kimi still has a narrower literal-chain brittleness point, and GPT plus Gemini are clean through `100`

That is a much sharper story than the original baseline gave us.
