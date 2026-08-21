# Flash + Luna V1.2 task-routed benchmark

> **Bounded result.** This report summarizes a fixed, task-only benchmark. Its
> latency and estimated inference cost are observations from this protocol and
> price snapshot, not production SLAs or production cost forecasts.

## Purpose

Validate the specialization suggested by the four-model benchmark: route three
structured routing/grading tasks to lower-cost Flash while keeping Luna on the
three tasks where the all-Flash profile lost checks.

The follow-up tests whether this fixed allocation preserves the Luna-all score
and reduces measured benchmark inference cost. It is not content-aware routing
and does not select a model dynamically per request.

## Protocol

| Item | Frozen setting |
|---|---|
| Protocol | `flash-luna-v1.2-three-rep-v1` |
| Scope | Task-only hybrid follow-up; six tasks, 10 cases per task |
| Profile | One fixed `flash_luna` allocation |
| Repetitions | 3, with a fresh process per repetition |
| Observations | 180 expected and completed |
| Temperature | `0` |
| Benchmark-level case retries | `0` |
| Generation scorer | `generation-lexical-v1.2` |
| Dataset | `model_optimization_cases_v1_1.jsonl` |

Each repetition executed 60 observations. The Luna-all comparison was read
from the retained four-model benchmark; it was not rerun for this follow-up.

## Fixed task routing

| Task | Provider | Exact model |
|---|---|---|
| Question Router | Together | `deepseek-ai/DeepSeek-V4-Flash-0731` |
| Retrieval Grader | Together | `deepseek-ai/DeepSeek-V4-Flash-0731` |
| Hallucination Grader | Together | `deepseek-ai/DeepSeek-V4-Flash-0731` |
| Answer Grader | OpenAI | `gpt-5.6-luna` |
| Generation | OpenAI | `gpt-5.6-luna` |
| Query Rewriter | OpenAI | `gpt-5.6-luna` |

## Overall results

| Scope | Passed | Estimated cost | p50 | p95 |
|---|---:|---:|---:|---:|
| Repetition 1 | 60/60 | $0.00442171 | 871.98 ms | 2,327.69 ms |
| Repetition 2 | 60/60 | $0.00409731 | 896.69 ms | 1,925.24 ms |
| Repetition 3 | 60/60 | $0.00393654 | 934.84 ms | 6,288.52 ms |
| **Total / overall** | **180/180** | **$0.01245556** | **908.37 ms** | **3,263.97 ms** |

All three repetitions scored 60/60. The overall mean latency was 1,298.33 ms;
the p50 and p95 are retained explicitly because the third repetition's tail
latency was materially higher than its median.

## Per-node results

| Task | Rep 1 | Rep 2 | Rep 3 | Total |
|---|---:|---:|---:|---:|
| Question Router | 10/10 | 10/10 | 10/10 | 30/30 |
| Retrieval Grader | 10/10 | 10/10 | 10/10 | 30/30 |
| Answer Grader | 10/10 | 10/10 | 10/10 | 30/30 |
| Generation | 10/10 | 10/10 | 10/10 | 30/30 |
| Hallucination Grader | 10/10 | 10/10 | 10/10 | 30/30 |
| Query Rewriter | 10/10 | 10/10 | 10/10 | 30/30 |

## Reliability

| Check | Result |
|---|---:|
| Completed observations | 180/180 |
| Provider/API errors | 0 |
| Structured-output errors | 0 |
| Failed checks | 0 |
| Pass/fail flips | 0 |
| Repetition score range / variance | 0 / 0 |

Provider-internal retries were unavailable, so no claim is made about them.
The evidence establishes clean completion for this bounded run, not a general
provider-availability guarantee.

## Token usage and estimated cost

| Provider / model | Observations | Input | Cached input | Output | Reasoning | Total | Cost |
|---|---:|---:|---:|---:|---:|---:|---:|
| OpenAI `gpt-5.6-luna` | 90 | 27,477 | 0 | 2,916 | 1,117 | 30,393 | $0.00899460 |
| Together `deepseek-ai/DeepSeek-V4-Flash-0731` | 90 | 30,396 | 9,880 | 1,044 | — | 31,440 | $0.00346096 |
| **Total** | **180** | — | — | — | — | — | **$0.01245556** |

Token values are provider-reported; a dash means the aggregate is not
meaningful or the provider did not expose that token field. Costs use the
frozen price snapshot and exclude non-inference production expenses.

## Baseline comparison

| Profile | Score | Estimated cost | p50 | p95 |
|---|---:|---:|---:|---:|
| Luna all | 180/180 | $0.01871220 | 914.10 ms | 2,090.38 ms |
| **Flash + Luna** | **180/180** | **$0.01245556** | **908.37 ms** | **3,263.97 ms** |
| GPT-5 mini baseline | 177/180 | $0.08051925 | 2,458.07 ms | 6,198.39 ms |

- Versus Luna all, the hybrid preserved 180/180 and reduced measured benchmark
  inference cost by **33.436154%**.
- Versus the formal GPT-5 mini benchmark baseline, the hybrid reduced measured
  benchmark inference cost by approximately **84.5%**. This is specifically a
  benchmark inference cost reduction, not a production cost-reduction claim.

## Trade-offs

The hybrid is not uniformly better than Luna all:

- It lowered measured cost and had a similar observed p50.
- Its observed p95 was worse: 3,263.97 ms versus Luna-all's 2,090.38 ms.
- It adds a second provider, credential boundary, client path, telemetry path,
  pricing surface, and operational dependency.

Consequently, `luna_all` and `flash_luna` are both meaningful
production-oriented profiles. `luna_all` favors one provider and the better
observed tail in this run; `flash_luna` favors lower measured benchmark
inference cost while retaining the bounded 180/180 score. The benchmark does
not support claiming that the hybrid is universally superior.

## Engineering decision

Retain the fixed hybrid as a selectable profile with no silent fallback, while
also retaining Luna all as the simpler single-provider profile. Selection is a
deployment trade-off, not a request-time model-routing decision.

The result validates the task split proposed by the
[four-model benchmark](four-model-v1.2.md), but it does not establish production
SLA, production cost, or behavior outside the frozen dataset.

## Retained evidence

- [Protocol](../../evals/flash_luna_v1_2_benchmark.json)
- [Dataset](../../evals/model_optimization_cases_v1_1.jsonl)
- [Generation scorer](../../evals/generation_lexical_v1_2.py)
- [Price snapshot](../../evals/four_model_six_node_v1_2_price_snapshot.json)
- [Retained summary](../../artifacts/flash-luna-v1.2-three-rep-summary.json)
- [Complete observations](../../artifacts/flash-luna-v1.2-three-rep-observations.jsonl)
- [Luna-all source summary](../../artifacts/four-model-six-node-v1.2-three-rep-summary.json)

The summary is the compact review surface; the JSONL file is the complete
observation-level audit trail.
