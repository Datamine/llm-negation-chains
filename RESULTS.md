# Negation Chain Results

## Overview

This repo now contains a set of related negation-chain experiments against four OpenRouter models:

- `openai/gpt-5.5-pro`
- `anthropic/claude-opus-4.7`
- `moonshotai/kimi-k2.6`
- `google/gemini-3.5-flash`

All of the main follow-up runs used a shared OpenRouter reasoning budget of `{"max_tokens": 65536}` so the models were allowed comparable maximum thinking effort. In practice, the models chose very different actual reasoning-token usage.

The core result across the whole project is:

1. Literal repeated `not not not ...` chains are much harder than count-based parity prompts.
2. Model behavior depends strongly on prompt shape, not just on the underlying parity problem.
3. There is evidence of priming / base-value effects when switching from `false` to `true`.
4. Some early failures in the first threaded harness run were infrastructure-related rather than pure reasoning failures.

## Data Files

The main completed result sets used in this writeup are:

- `Answers/boolean_literal_false-answers.csv`
- `Answers/boolean_counted_false_targeted-answers.csv`
- `Answers/boolean_literal_true_sequential-answers.csv`
- `Answers/sentiment_literal_targeted-answers.csv`
- `Answers/lock_literal_targeted-answers.csv`

Aggregate summaries are in:

- `Reports/negation_suite_summary.csv`
- `Reports/negation_suite_by_negation.csv`

Visuals are in:

- `Visualizations/negation-suite-accuracy-panels.png`
- `Visualizations/negation-suite-reasoning-token-panels.png`
- `Visualizations/negation-suite-boolean-priming-comparison.png`
- `Visualizations/negation-suite-accuracy-heatmap.png`

## Methodology

### 1. Boolean Literal False Base

File:

- `Answers/boolean_literal_false-answers.csv`

Prompt form:

- literal repeated negation chain ending in `false`
- counts tested: `0..20`, then `50`, `51`, `100`, `101`, `500`, `501`

This was the main baseline. It ran through the general answer harness. Because that harness used concurrent model execution and timeouts, this dataset mixes genuine reasoning failures with some infrastructure artifacts such as timeouts and one rate-limit-style error.

### 2. Boolean Counted False Base

File:

- `Answers/boolean_counted_false_targeted-answers.csv`

Prompt form:

- asks directly about the result of applying `not` exactly `N` times to `false`
- counts tested: `50`, `51`, `100`, `101`, `500`, `501`, `1000`, `1001`, `10000`, `10001`

This is the cleanest control condition. It removes the long repeated token chain from the prompt while preserving the parity task.

### 3. Boolean Literal True Base

File:

- `Answers/boolean_literal_true_sequential-answers.csv`

Prompt form:

- same literal repeated chain, but ending in `true`
- completed counts: `0..20`, `50`, `51`, `100`

This run was done sequentially to reduce the infrastructure issues seen in the original threaded baseline. It is partial: the higher counts beyond `100` did not complete.

### 4. Sentiment Literal

File:

- `Answers/sentiment_literal_targeted-answers.csv`

Prompt form:

- “The movie review is not not ... positive. Is the sentiment positive or negative?”
- counts tested: `0`, `1`, `2`, `5`, `10`, `20`, `50`, `51`

### 5. Lock State Literal

File:

- `Answers/lock_literal_targeted-answers.csv`

Prompt form:

- “The vault door is not not ... locked. Is the door locked or unlocked?”
- counts tested: `0`, `1`, `2`, `5`, `10`, `20`, `50`, `51`

## Headline Findings

### A. Counted prompts are dramatically easier than literal repeated-token chains

This is the strongest result in the entire project.

On the counted prompt:

- GPT-5.5-Pro: `100%` over 10 targeted counts
- Gemini 3.5 Flash: `100%`
- Kimi K2.6: `100%`
- Claude Opus 4.7: `90%` with a single miss at `1000`

On the literal `false` base baseline:

- GPT-5.5-Pro: `74.07%`
- Gemini 3.5 Flash: `96.3%`
- Kimi K2.6: `77.78%`
- Claude Opus 4.7: `81.48%`

That difference is too large to explain as simple parity difficulty. The most likely interpretation is that repeated literal negation tokens create a separate failure mode involving prompt length, repeated-token handling, or chain parsing.

### B. Gemini was the strongest overall on literal chains

Gemini had the best performance on the literal `false` base baseline and the cleanest behavior across the follow-up tasks:

- `96.3%` on `boolean_literal_false`
- `100%` on the completed `boolean_literal_true` sequential overlap
- `100%` on `sentiment_literal_targeted`
- `100%` on `lock_literal_targeted`

Its most notable literal-chain miss was:

- wrong at `501` on the `false`-base literal chain

So Gemini was the strongest overall, but not perfect.

### C. Claude showed genuine semantic/parity errors even when infrastructure was not the issue

Claude’s failures were not just timeouts.

Examples:

- `boolean_literal_false`: wrong at `5`, `7`, `51`
- `boolean_literal_true`: wrong at `7`, `10`, `100`
- `sentiment_literal_targeted`: wrong at `50`
- `lock_literal_targeted`: wrong at `5`
- `boolean_counted_false_targeted`: wrong at `1000`

This matters because Claude often used very few or zero reported reasoning tokens, yet still made confident wrong answers on relatively modest counts.

### D. Kimi was unstable around the higher literal counts and often produced inadmissible or wrong outputs

Kimi’s profile was:

- good on the counted task
- good on many lower literal counts
- unstable on harder literal chains

Examples:

- `boolean_literal_false`: inadmissible at `8`, then timeouts/inadmissibles at several larger counts
- `boolean_literal_true`: wrong at `51`
- `sentiment_literal_targeted`: inadmissible at `50`, wrong at `51`
- `lock_literal_targeted`: wrong at `51`

Kimi also showed some of the largest reasoning-token spikes among the successful runs.

### E. GPT-5.5-Pro’s early literal-chain failures were partly harness artifacts

The first threaded baseline made GPT look much worse than the later sequential runs suggest.

In the threaded `false`-base baseline, GPT had:

- inadmissible / error at `16`
- timeouts at `50`, `51`, `100`, `500`, `501`
- a JSON decode failure at `101`

But in the sequential `true`-base run, GPT was:

- correct through every completed count, including `50`, `51`, and `100`

This does not prove GPT would be perfect on the `false` base under a clean sequential rerun, but it does show that the original threaded run overstated its weakness.

## Per-Dataset Results

### Boolean Literal False Base

Summary:

- GPT-5.5-Pro: `74.07%`, `25.93%` inadmissible
- Claude Opus 4.7: `81.48%`, `7.41%` inadmissible
- Kimi K2.6: `77.78%`, `22.22%` inadmissible
- Gemini 3.5 Flash: `96.3%`, `0%` inadmissible

First non-perfect count:

- Claude: `5`
- Kimi: `8`
- GPT: `16`
- Gemini: `501`

Notable individual failures:

- Claude: wrong at `5`, `7`, `51`
- Kimi: inadmissible at `8`
- GPT: error/inadmissible at `16`, then multiple timeout-driven misses later
- Gemini: wrong at `501`

Interpretation:

- This dataset established that literal chains are hard.
- It also established that the harness itself can distort results once concurrency, timeouts, and provider-side issues begin to matter.

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
- The hard part is the literal textual realization of the chain, not the parity mapping.

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

- Switching the base from `false` to `true` changed the error pattern.
- That is evidence for a real priming / prompt-path effect, not just a fixed parity threshold.

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

- The same negation structure is easier when wrapped in a “positive/negative” sentiment frame than in raw boolean syntax.
- GPT and Gemini were completely stable on this slice.

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

- Task framing matters a lot.
- Claude was worse here at low counts than it was on sentiment.

## Priming Effect: False Base vs True Base

The cleanest comparison is on the overlap between the completed `false`-base and `true`-base literal runs:

- completed overlap: `0..20`, `50`, `51`, `100`
- total overlapping counts per model: `24`

Accuracy on the overlap:

- Claude: `20/24` on `false` base vs `21/24` on `true` base
- Gemini: `24/24` vs `24/24`
- Kimi: `21/24` vs `23/24`
- GPT: `20/24` vs `24/24`

Counts where the outcome changed:

- Claude: `5`, `10`, `51`, `100`
- Kimi: `8`, `50`, `51`
- GPT: `16`, `50`, `51`, `100`
- Gemini: none on the overlap

Interpretation:

- There is strong evidence that base value matters.
- Some of GPT’s apparent priming effect is probably really a harness-quality effect, because its `false`-base misses were often infrastructure errors rather than clean wrong answers.
- Claude and Kimi still show real prompt-path dependence even after accounting for that.

## Thinking-Token Behavior

### Literal False Base

Mean reasoning tokens:

- Claude: `65.76`
- Gemini: `2027.93`
- Kimi: `996.14`
- GPT: `218.45`

Examples of growth:

- Gemini: `138` at `0`, `2121` at `50`, `4825` at `100`, `22781` at `500`
- Kimi: `70` at `0`, `528` at `20`, `12347` at `100`
- Claude: `0` for many low counts, then `142` at `50`, `602` at `501`

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
- This is another reason to think the repeated literal chain itself is the main source of difficulty.

### True Base vs False Base

Mean reasoning tokens:

- GPT: `218.45` on `false` base vs `407.71` on completed `true` base
- Claude: `65.76` vs `42.04`
- Kimi: `996.14` vs `2124.88`
- Gemini: `2027.93` vs `643.29`

Interpretation:

- Token usage is highly prompt-path dependent.
- The same logical task can induce very different internal effort depending on wording and base value.

## Reliability and Caveats

### 1. The original threaded baseline contains infrastructure artifacts

`boolean_literal_false-answers.csv` includes:

- timeout-generated inadmissibles
- at least one apparent rate-limit / malformed-response error
- concurrent model execution effects

So that dataset is still valuable, but it should not be read as a pure measure of reasoning quality.

### 2. The sequential follow-ups are more reliable

The counted task, sentiment task, lock task, and the completed part of the `true`-base run are better indicators of actual model behavior because they were run sequentially and produced fewer harness-side artifacts.

### 3. The `true`-base run is partial

The sequential `boolean_literal_true` run completed only through:

- `0..20`
- `50`
- `51`
- `100`

It did not finish `101`, `500`, or `501`.

### 4. The parking follow-up is partial and excluded from the main conclusions

There is a partial file:

- `Answers/parking_literal_targeted-answers.csv`

But it stalled and was not clean enough to use as one of the main headline datasets.

## Overall Interpretation

The evidence currently supports the following model:

1. Models generally understand the parity rule.
2. Literal repeated negation chains introduce a separate failure mode that is not captured by simple count-based tests.
3. Prompt framing materially changes both accuracy and thinking-token usage.
4. Base truth value (`true` vs `false`) can change behavior, especially for Claude and Kimi, and maybe GPT as well once infrastructure artifacts are removed.
5. Gemini was the strongest overall in this set, especially on literal chains.
6. GPT likely performs better than the first threaded baseline suggested.
7. Claude is vulnerable to clean semantic/parity flips even at moderate counts and across multiple framings.
8. Kimi often spends a lot of reasoning tokens and still destabilizes on harder literal-chain variants.

## Best Current Summary By Model

### GPT-5.5-Pro

- Likely strong on the actual task when run cleanly
- Perfect on counted, sentiment, lock, and completed `true`-base sequential data
- First baseline underestimated it because of infrastructure failures

### Claude Opus 4.7

- Often uses very low reported reasoning-token counts
- Makes genuine wrong answers across several tasks
- Error locations shift with prompt framing and base value

### Kimi K2.6

- Strong on counted prompts
- Unstable on literal high-count prompts
- Can spend very large reasoning-token budgets without staying reliable

### Gemini 3.5 Flash

- Strongest overall
- Best literal-chain performance
- Still not literally perfect, with a notable miss at `501` on the `false`-base literal chain

## Most Important Next Experiments

If this work continues, the highest-value next steps are:

1. Rerun the `boolean_literal_false` baseline sequentially for all models.
2. Run mirrored `true`-base versions of `sentiment_literal` and `lock_literal`.
3. Add more “semantic wrapper” tasks like permission, temperature, safety, and polarity.
4. Separate timeout/infrastructure failures from reasoning failures in the reporting.
5. Add direct latency measurements next to reasoning-token counts.

## Bottom Line

The main result is not just that some models fail long negation chains. It is that there are at least three separable phenomena:

1. parity reasoning
2. literal repeated-token chain handling
3. prompt framing / priming

The counted task shows parity itself is mostly easy. The literal-chain tasks show the real brittleness. The `true` vs `false` comparison and the sentiment / lock variations show that prompt shape and semantic framing matter enough to move both accuracy and internal token usage in large ways.
