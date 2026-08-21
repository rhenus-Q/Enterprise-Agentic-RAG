# Evals

The repository keeps two distinct forms of evaluation evidence:

- The general behavioral harness drives the real graph over the synthetic
  enterprise corpus and applies deterministic checks.
- The last two formal model benchmarks are frozen, Git-managed evidence. Their
  paid runners and earlier experiment scaffolding are intentionally not kept.

No LLM-as-judge is used by the retained workflows.

## Files

| File | Purpose |
|---|---|
| `questions.jsonl` | General behavioral dataset: 24 rows across local-corpus, web-fallback, insufficient-context, privacy, multi-document, and fallback-policy cases. |
| `run_eval.py` | General runner: invokes the graph, checks behavior, aggregates provider usage, optionally estimates cost, and writes the report/history. |
| `model_pricing.py` | Pure cost calculation from exact provider/model usage and an explicit reviewed price snapshot. It performs no network lookup. |
| `results.md` | Generated behavioral-eval report. |
| `history/.gitkeep` | Keeps the gitignored append-only history directory present in a clone. |
| `four_model_six_node_v1_2_benchmark.json` | Frozen four-model × six-node × three-repetition protocol. |
| `flash_luna_v1_2_benchmark.json` | Frozen Flash + Luna × six-node × three-repetition hybrid protocol. |
| `four_model_six_node_v1_2_price_snapshot.json` | Explicit reviewed price snapshot shared by both formal benchmarks. |
| `model_optimization_cases_v1_1.jsonl` | Frozen 10-cases-per-task dataset referenced by both protocols. |
| `generation_lexical_v1_2.py` | Frozen Generation scorer referenced by both protocols. |
| `generation_lexical_v1_1.py` | Normalization dependency required by the V1.2 scorer. |
| `../artifacts/*v1.2-three-rep-observations.jsonl` | Complete formal observations for the two retained runs. |
| `../artifacts/*v1.2-three-rep-summary.json` | Machine-readable summaries and conclusions for the two retained runs. |

## Behavioral dataset and checks

Required fields in each `questions.jsonl` row are `id`, `category`, `question`,
`web_search_enabled`, and `expected_behavior`. Optional deterministic contracts
include:

- `expected_stop_reason`
- `expected_source_type`
- `expected_contains` and `expected_not_contains`
- `expected_source_titles` and `expected_min_local_sources`
- `expected_web_search_count`
- `web_fallback_policy`

Per-row checks cover stop reasons, source type/provenance, expected answer
substrings, web-search counts, and effective fallback policy. Privacy rows also
prove that a disabled web path stays disabled. History records remain
metadata-only: they do not store prompts, document bodies, raw graph state, or
answer text.

## Running the behavioral harness

```powershell
# Schema validation only; no provider calls and no history write
uv run python evals/run_eval.py --validate-only

# Full behavioral eval; REAL configured-provider calls and, when enabled, Tavily
uv run python evals/run_eval.py

# Focused run; no automatic history write or baseline discovery
uv run python evals/run_eval.py --limit 3

# Use an explicitly reviewed price snapshot for local cost calculation
uv run python evals/run_eval.py --price-snapshot <reviewed-snapshot.json>

# Keep report output metadata-only
uv run python evals/run_eval.py --metadata-only
```

Cloud credentials depend on the selected model profile and provider
configuration. Local mode uses the configured Ollama-compatible endpoint;
Tavily is called only when the effective run enables web search.

The formal model benchmarks must not be rerun as part of ordinary validation.
Their paid runners were experimental scaffolding and have been removed; the
retained protocol, input hashes, observations, summaries, and contract tests
are the evidence surface.

## Provider usage and cost accounting

The graph collector records actual provider response metadata for every model
attempt:

- `input_tokens`
- `cached_input_tokens`
- `cache_write_tokens`
- `output_tokens`
- `reasoning_tokens`
- `total_tokens`
- latency, provider, requested model, and reported model
- requested/effective profile, task, tier, settings, and completion status

Missing provider fields remain `null`; no local tokenizer is used to invent
usage. `model_pricing.py` accepts only an explicit snapshot whose entries are
keyed by exact `(provider, model)` pairs. It supports cached input, cache write,
output, and frozen long-context rates. A missing price or required token field
makes the estimate incomplete rather than silently treating the value as zero.

## Retained formal benchmark evidence

### Four-model × six-node × three reps

The frozen protocol evaluated four historical all-node benchmark arms across
all six model tasks, 10 cases per task, and three repetitions: 720 observations
in total. It recorded 702 passes and 18 failures with no provider API or
structured-output errors. Luna All achieved 180/180; the other historical arms
remain visible only inside this frozen evidence and are not selectable runtime
profiles.

Git-managed evidence:

- `four_model_six_node_v1_2_benchmark.json`
- `four_model_six_node_v1_2_price_snapshot.json`
- `model_optimization_cases_v1_1.jsonl`
- `generation_lexical_v1_1.py`
- `generation_lexical_v1_2.py`
- `../artifacts/four-model-six-node-v1.2-three-rep-observations.jsonl`
- `../artifacts/four-model-six-node-v1.2-three-rep-summary.json`

### Flash + Luna × six-node × three reps

The final hybrid protocol fixes the selectable `flash_luna` runtime allocation
exactly:

- Flash: `question_router`, `retrieval_grader`, `hallucination_grader`
- Luna: `answer_grader`, `generation`, `query_rewriter`

All 180 observations passed, with no provider API or structured-output errors.
The frozen summary estimates total cost at `$0.01245556`, 33.436154% below the
retained Luna All comparison, while preserving the same 180/180 task score.

Git-managed evidence:

- `flash_luna_v1_2_benchmark.json`
- the shared price snapshot, dataset, and scorer files listed above
- `../artifacts/flash-luna-v1.2-three-rep-observations.jsonl`
- `../artifacts/flash-luna-v1.2-three-rep-summary.json`

The protocol files also name ignored local Markdown reports under `Doc/`.
Those ignored files are outside Git evidence and are not read, modified,
deleted, or added by repository cleanup or validation.

## History and delta reporting

A full general eval can append a compact JSON record under `evals/history/`.
The loader compares the current run with the latest compatible baseline and
reports dataset changes, aggregate deltas, and per-row transitions. `--limit`
runs do not write or auto-discover history; `--no-history`, `--baseline`, and
`--history-dir` provide explicit control.

Generated history JSON is gitignored by default. Records are metadata-only and
include dataset fingerprints, sanitized usage attempts, metrics, effective
model targets, counters, and optional cost. They never include document bodies,
prompts, secrets, raw state, or generated answers.

## Why full evals are not in CI

Full behavioral runs need real services, cost money, and are nondeterministic.
CI runs only mocked helper and contract tests. The retained formal evidence is
validated locally by schema, count, mapping, and SHA-256 contracts without any
provider call.
