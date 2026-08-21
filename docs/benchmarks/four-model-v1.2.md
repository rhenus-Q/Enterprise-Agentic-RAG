# Four-model, six-node V1.2 benchmark

> **Bounded result.** This report summarizes a fixed, task-only benchmark. Its
> latency and estimated inference cost are observations from this protocol and
> price snapshot, not production SLAs or production cost forecasts.

## Purpose

Compare four all-node model profiles across the six chat tasks used by the RAG
graph, then identify an allocation that improves correctness and measured
benchmark inference cost without relying on anecdotal model preference.

The benchmark answers two engineering questions:

1. Which single model is the strongest all-node replacement for the legacy
   `gpt-5-mini` profile on this fixed task set?
2. Do individual nodes reveal a lower-cost specialization worth validating as
   a separately routed profile?

## Protocol

| Item | Frozen setting |
|---|---|
| Protocol | `four-model-six-node-v1.2-three-rep-v1` |
| Scope | Task-only; six tasks, 10 cases per task |
| Profiles | 4 all-node profiles |
| Repetitions | 3, with a fresh process per profile/repetition |
| Observations | 720 expected and completed |
| Temperature | `0` |
| Benchmark-level case retries | `0` |
| Generation scorer | `generation-lexical-v1.2` |
| Dataset | `model_optimization_cases_v1_1.jsonl` |

Each profile therefore produced 180 observations: six tasks × 10 cases ×
three repetitions. Provider-internal retries were not exposed by the APIs.

## Profiles

| Profile | Provider | Exact model | Allocation |
|---|---|---|---|
| `flash_all` | Together | `deepseek-ai/DeepSeek-V4-Flash-0731` | All six tasks |
| `luna_all` | OpenAI | `gpt-5.6-luna` | All six tasks |
| `legacy` | OpenAI | `gpt-5-mini` | All six tasks |
| `pro_all` | Together | `deepseek-ai/DeepSeek-V4-Pro-0813` | All six tasks |

## Overall results

| Profile | Rep 1 | Rep 2 | Rep 3 | Total | Estimated cost | p50 | p95 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Flash | 57/60 | 56/60 | 59/60 | **172/180** | **$0.00671443** | 656.76 ms | 2,147.69 ms |
| Luna | 60/60 | 60/60 | 60/60 | **180/180** | **$0.01871220** | 914.10 ms | 2,090.38 ms |
| GPT-5 mini | 59/60 | 59/60 | 59/60 | **177/180** | **$0.08051925** | 2,458.07 ms | 6,198.39 ms |
| Pro | 58/60 | 58/60 | 57/60 | **173/180** | **$0.09314360** | 4,615.00 ms | 22,544.41 ms |

Luna was the only all-node model to reach 180/180. Relative to the GPT-5 mini
baseline, Luna improved the score from 177/180 to 180/180 while reducing
measured benchmark inference cost by approximately **76.8%**.

Flash was the least expensive profile and had the lowest observed p50, but its
172/180 score and 2,147.69 ms p95 show why neither cost nor median latency alone
was used as the selection criterion.

## Per-node results

| Task | Flash | Luna | GPT-5 mini | Pro |
|---|---:|---:|---:|---:|
| Question Router | **30/30** | 30/30 | 30/30 | 29/30 |
| Retrieval Grader | **30/30** | 30/30 | 29/30 | 30/30 |
| Answer Grader | 27/30 | 30/30 | 28/30 | 24/30 |
| Generation | 26/30 | 30/30 | 30/30 | 30/30 |
| Hallucination Grader | **30/30** | 30/30 | 30/30 | 30/30 |
| Query Rewriter | 29/30 | 30/30 | 30/30 | 30/30 |

The specialization signal was clear: Flash scored 30/30 on Question Router,
Retrieval Grader, and Hallucination Grader, while its losses were concentrated
in Answer Grader, Generation, and one Query Rewriter observation.

## Reliability and failures

| Check | Result |
|---|---:|
| Completed observations | 720/720 |
| Provider/API errors | 0 |
| Structured-output errors | 0 |
| Failed checks | 18 |
| Luna pass/fail flips | 0 |
| GPT-5 mini repetition scores | 59, 59, 59 |
| Flash repetition range | 3 observations (57, 56, 59) |

The largest shared failure was `usefulness-06-wrong-topic-detail`: eight
Answer Grader failures across Flash, GPT-5 mini, and Pro. Pro also missed
`usefulness-09-injected-valid-answer` in all three repetitions.

Flash had four Generation failures across two repeated cases and one legitimate
Query Rewriter miss. Single one-off misses also appeared in Pro's Question
Router and GPT-5 mini's Retrieval Grader. Luna had no failed observation in
this bounded run.

## Token usage and estimated cost

Token values are provider-reported. A dash means that provider did not expose
that field; cached-input tokens are included separately for auditability.

| Profile | Input | Cached input | Output | Reasoning | Total | Estimated cost |
|---|---:|---:|---:|---:|---:|---:|
| Flash | 55,065 | 15,345 | 2,476 | — | 57,541 | $0.00671443 |
| Luna | 67,245 | 0 | 4,386 | 1,245 | 71,631 | $0.01871220 |
| GPT-5 mini | 67,245 | 0 | 31,854 | 27,200 | 99,099 | $0.08051925 |
| Pro | 55,065 | 19,184 | 10,931 | 8,508 | 65,996 | $0.09314360 |

Costs use the benchmark's frozen price snapshot and observed token usage. They
exclude application infrastructure, retrieval, web search, engineering, and
operational costs.

## Engineering decision

The evidence supported two follow-up decisions:

- Adopt `luna_all` as the strongest single-model cloud profile in this test:
  it was the only 180/180 profile and materially reduced measured benchmark
  inference cost versus the legacy GPT-5 mini baseline.
- Validate a task-routed **Flash + Luna** profile: use Flash only on the three
  nodes where it scored 30/30, and retain Luna for Answer Grader, Generation,
  and Query Rewriter.

That hybrid hypothesis was tested separately in
[Flash + Luna V1.2](flash-luna-v1.2.md). This benchmark does not establish
production reliability, tail-latency guarantees, or future provider pricing.

## Retained evidence

- [Protocol](../../evals/four_model_six_node_v1_2_benchmark.json)
- [Dataset](../../evals/model_optimization_cases_v1_1.jsonl)
- [Generation scorer](../../evals/generation_lexical_v1_2.py)
- [Price snapshot](../../evals/four_model_six_node_v1_2_price_snapshot.json)
- [Retained summary](../../artifacts/four-model-six-node-v1.2-three-rep-summary.json)
- [Complete observations](../../artifacts/four-model-six-node-v1.2-three-rep-observations.jsonl)

The summary is the compact review surface; the JSONL file is the complete
observation-level audit trail.
