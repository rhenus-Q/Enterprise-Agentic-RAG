"""Offline integrity contracts for the two retained formal benchmarks."""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from collections import Counter
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]

TASKS = {
    "question_router",
    "retrieval_grader",
    "answer_grader",
    "generation",
    "hallucination_grader",
    "query_rewriter",
}

GENERATION_LEXICAL_V1_1 = {
    "path": "evals/generation_lexical_v1_1.py",
    "sha256": "c9d60a8550eb59095fd435ab44216c76db93004947b295574f80fd0e3cdaf27b",
}

HISTORICAL_LUNA_ALL_SOURCE = {
    "path": "artifacts/four-model-six-node-v1.2-three-rep-summary.json",
    "sha256": "75852f2a3c280f11a62bd2d9f34cb32838733ad1e0d9a07fcf00e34d75a172c4",
    "benchmark_protocol": "four-model-six-node-v1.2-three-rep-v1",
    "profile": "luna_all",
}

RETAINED_FOUR_MODEL_SUMMARY = {
    "path": "artifacts/four-model-six-node-v1.2-three-rep-summary.json",
    "sha256": "3991ab6dc25d9193cd237cb0cce00e993a0968907f16dc11f54d5a3e75893aed",
}

TOKEN_FIELDS = (
    "input_tokens",
    "cached_input_tokens",
    "cache_write_tokens",
    "output_tokens",
    "reasoning_tokens",
    "total_tokens",
)

FLASH_LUNA_TARGETS = {
    "question_router": ("together", "deepseek-ai/DeepSeek-V4-Flash-0731"),
    "retrieval_grader": ("together", "deepseek-ai/DeepSeek-V4-Flash-0731"),
    "answer_grader": ("openai", "gpt-5.6-luna"),
    "generation": ("openai", "gpt-5.6-luna"),
    "hallucination_grader": ("together", "deepseek-ai/DeepSeek-V4-Flash-0731"),
    "query_rewriter": ("openai", "gpt-5.6-luna"),
}

BENCHMARKS = (
    {
        "protocol": "evals/four_model_six_node_v1_2_benchmark.json",
        "observations": "artifacts/four-model-six-node-v1.2-three-rep-observations.jsonl",
        "summary": "artifacts/four-model-six-node-v1.2-three-rep-summary.json",
        "protocol_id": "four-model-six-node-v1.2-three-rep-v1",
        "profiles": {"flash_all", "luna_all", "legacy", "pro_all"},
        "observations_count": 720,
        "passed": 702,
        "failed": 18,
    },
    {
        "protocol": "evals/flash_luna_v1_2_benchmark.json",
        "observations": "artifacts/flash-luna-v1.2-three-rep-observations.jsonl",
        "summary": "artifacts/flash-luna-v1.2-three-rep-summary.json",
        "protocol_id": "flash-luna-v1.2-three-rep-v1",
        "profiles": {"flash_luna"},
        "observations_count": 180,
        "passed": 180,
        "failed": 0,
    },
)


def _path(relative: str) -> Path:
    return PROJECT_ROOT / relative


def _load_json(relative: str) -> dict[str, Any]:
    return json.loads(_path(relative).read_text(encoding="utf-8"))


def _load_jsonl(relative: str) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in _path(relative).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _sha256(relative: str) -> str:
    """Hash Git-normalized text so pins are independent of checkout EOLs."""

    content = _path(relative).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(content).hexdigest()


def _sum_cost(rows: list[dict[str, Any]]) -> float:
    return float(sum((Decimal(str(row["estimated_cost_usd"])) for row in rows), Decimal(0)))


def _sum_known(rows: list[dict[str, Any]], field: str) -> int | None:
    values = [row[field] for row in rows if row.get(field) is not None]
    return sum(int(value) for value in values) if values else None


def _latency_metrics(rows: list[dict[str, Any]]) -> dict[str, float | int]:
    values = sorted(float(row["latency_ms"]) for row in rows)

    def percentile(fraction: float) -> float:
        index = max(0, math.ceil(fraction * len(values)) - 1)
        return round(values[index], 2)

    return {
        "count": len(values),
        "mean": round(statistics.fmean(values), 2),
        "p50": percentile(0.50),
        "p95": percentile(0.95),
    }


def test_retained_generation_v1_1_dependency_is_hash_pinned():
    assert _path(GENERATION_LEXICAL_V1_1["path"]).is_file()
    assert _sha256(GENERATION_LEXICAL_V1_1["path"]) == GENERATION_LEXICAL_V1_1["sha256"]


@pytest.mark.parametrize("benchmark", BENCHMARKS, ids=lambda item: item["protocol_id"])
def test_retained_protocol_and_summary_references_are_hash_pinned(benchmark):
    protocol = _load_json(benchmark["protocol"])
    summary = _load_json(benchmark["summary"])

    assert protocol["schema_version"] == 1
    assert protocol["protocol_id"] == benchmark["protocol_id"]
    assert set(protocol["tasks"]) == TASKS
    assert protocol["repetitions"] == 3
    assert protocol["expected_observations"] == benchmark["observations_count"]

    for reference_name in ("generation_scorer", "task_dataset", "price_snapshot"):
        reference = protocol[reference_name]
        path_key = "spec_path" if reference_name == "generation_scorer" else "path"
        hash_key = "spec_sha256" if reference_name == "generation_scorer" else "sha256"
        assert _path(reference[path_key]).is_file()
        assert _sha256(reference[path_key]) == reference[hash_key]
        assert summary[reference_name] == reference

    assert summary["summary_schema_version"] == 1
    assert summary["benchmark_protocol"] == benchmark["protocol_id"]
    assert summary["protocol_file"] == benchmark["protocol"]
    assert summary["protocol_sha256"] == _sha256(benchmark["protocol"])
    assert summary["expected_observations"] == benchmark["observations_count"]
    assert summary["observations"] == benchmark["observations_count"]
    assert summary["completed_observations"] == benchmark["observations_count"]
    assert summary["passed"] == benchmark["passed"]
    assert summary["failed"] == benchmark["failed"]
    assert summary["provider_api_errors"] == 0
    assert summary["structured_output_errors"] == 0

    assert protocol["artifacts"]["observations_jsonl"] == benchmark["observations"]
    assert protocol["artifacts"]["summary_json"] == benchmark["summary"]


def test_luna_all_historical_pin_and_retained_source_are_distinct():
    protocol = _load_json("evals/flash_luna_v1_2_benchmark.json")
    flash_summary = _load_json("artifacts/flash-luna-v1.2-three-rep-summary.json")

    assert protocol["luna_all_comparison"] == HISTORICAL_LUNA_ALL_SOURCE
    assert flash_summary["luna_all_comparison"]["source"] == HISTORICAL_LUNA_ALL_SOURCE
    assert _sha256(RETAINED_FOUR_MODEL_SUMMARY["path"]) == RETAINED_FOUR_MODEL_SUMMARY["sha256"]
    assert HISTORICAL_LUNA_ALL_SOURCE["sha256"] != RETAINED_FOUR_MODEL_SUMMARY["sha256"]


@pytest.mark.parametrize("benchmark", BENCHMARKS, ids=lambda item: item["protocol_id"])
def test_retained_observations_have_complete_schema_and_schedule(benchmark):
    observations = _load_jsonl(benchmark["observations"])

    assert len(observations) == benchmark["observations_count"]
    assert {item["benchmark_protocol"] for item in observations} == {benchmark["protocol_id"]}
    assert {item["profile"] for item in observations} == benchmark["profiles"]
    assert {item["task"] for item in observations} == TASKS
    assert {item["repetition"] for item in observations} == {1, 2, 3}

    schedule_counts = Counter(
        (item["profile"], item["task"], item["repetition"]) for item in observations
    )
    assert set(schedule_counts.values()) == {10}
    assert len(schedule_counts) == len(benchmark["profiles"]) * len(TASKS) * 3

    required_fields = {
        "artifact_schema_version",
        "benchmark_run_id",
        "case_id",
        "completed",
        "cost_status",
        "estimated_cost_usd",
        "input_tokens",
        "cached_input_tokens",
        "cache_write_tokens",
        "output_tokens",
        "reasoning_tokens",
        "total_tokens",
        "latency_ms",
        "provider",
        "requested_model",
        "reported_models",
        "usage_attempts",
        "usage_complete",
    }
    attempt_fields = {
        "input_tokens",
        "cached_input_tokens",
        "cache_write_tokens",
        "output_tokens",
        "reasoning_tokens",
        "total_tokens",
        "duration_ms",
        "provider",
        "requested_model",
        "reported_model",
        "requested_profile",
        "effective_profile",
        "task",
        "status",
    }

    for observation in observations:
        assert required_fields <= observation.keys()
        assert observation["artifact_schema_version"] == 1
        assert observation["completed"] is True
        assert observation["cost_status"] == "complete"
        assert observation["usage_complete"] is True
        assert observation["latency_ms"] >= 0
        assert observation["usage_attempts"]
        for attempt in observation["usage_attempts"]:
            assert attempt_fields <= attempt.keys()


def test_four_model_summary_aggregates_the_retained_observations():
    protocol = _load_json("evals/four_model_six_node_v1_2_benchmark.json")
    summary = _load_json(RETAINED_FOUR_MODEL_SUMMARY["path"])
    observations = _load_jsonl("artifacts/four-model-six-node-v1.2-three-rep-observations.jsonl")

    for profile in protocol["profiles"]:
        profile_rows = [row for row in observations if row["profile"] == profile]
        model = summary["models"][profile]
        rep_scores = []

        assert model["passed"] == sum(row["passed"] for row in profile_rows)
        assert model["total"] == len(profile_rows)
        assert model["completed_calls"] == sum(row["completed"] for row in profile_rows)
        assert model["provider_api_errors"] == sum(
            row["provider_api_error"] for row in profile_rows
        )
        assert model["structured_output_errors"] == sum(
            row["structured_output_error"] for row in profile_rows
        )
        assert model["usage_complete_observations"] == sum(
            row["usage_complete"] for row in profile_rows
        )
        assert model["tokens"] == {field: _sum_known(profile_rows, field) for field in TOKEN_FIELDS}
        assert model["estimated_cost_usd"] == _sum_cost(profile_rows)
        assert model["latency_ms"] == _latency_metrics(profile_rows)

        for repetition in (1, 2, 3):
            rep_rows = [row for row in profile_rows if row["repetition"] == repetition]
            rep_summary = model["repetitions"][str(repetition)]
            rep_passed = sum(row["passed"] for row in rep_rows)
            rep_scores.append(rep_passed)

            assert rep_summary["passed"] == rep_passed
            assert rep_summary["total"] == len(rep_rows)
            assert rep_summary["cost_usd"] == _sum_cost(rep_rows)
            assert rep_summary["latency_ms"] == _latency_metrics(rep_rows)

        assert model["stability"] == {
            "rep_scores": rep_scores,
            "score_range": max(rep_scores) - min(rep_scores),
            "score_variance": round(statistics.pvariance(rep_scores), 6),
        }

        for task in TASKS:
            task_rows = [row for row in profile_rows if row["task"] == task]
            passed = sum(row["passed"] for row in task_rows)
            assert summary["by_node"][task][profile] == {
                "passed": passed,
                "total": len(task_rows),
                "pass_rate": round(passed / len(task_rows), 6),
                "repetitions": {
                    str(repetition): sum(
                        row["passed"] for row in task_rows if row["repetition"] == repetition
                    )
                    for repetition in (1, 2, 3)
                },
            }

    assert summary["cost"] == {
        "estimated_total_usd": _sum_cost(observations),
        "status": "complete",
    }
    assert summary["latency_ms"] == _latency_metrics(observations)
    assert summary["models"]["luna_all"]["passed"] == 180
    assert summary["models"]["luna_all"]["total"] == 180


def test_flash_luna_protocol_observations_and_summary_pin_the_exact_six_node_mapping():
    protocol = _load_json("evals/flash_luna_v1_2_benchmark.json")
    summary = _load_json("artifacts/flash-luna-v1.2-three-rep-summary.json")
    four_model_summary = _load_json(RETAINED_FOUR_MODEL_SUMMARY["path"])
    observations = _load_jsonl("artifacts/flash-luna-v1.2-three-rep-observations.jsonl")

    protocol_targets = {
        task: (target["provider"], target["model"])
        for task, target in protocol["profiles"]["flash_luna"]["task_targets"].items()
    }
    summary_targets = {
        task: (target["provider"], target["model"]) for task, target in summary["by_node"].items()
    }
    observed_targets = {
        task: {
            (item["provider"], item["requested_model"])
            for item in observations
            if item["task"] == task
        }
        for task in TASKS
    }

    assert protocol_targets == FLASH_LUNA_TARGETS
    assert summary_targets == FLASH_LUNA_TARGETS
    assert observed_targets == {task: {target} for task, target in FLASH_LUNA_TARGETS.items()}
    assert summary["cost"] == {
        "estimated_total_usd": 0.01245556,
        "status": "complete",
    }
    luna = four_model_summary["models"]["luna_all"]
    comparison = summary["luna_all_comparison"]
    assert comparison == {
        "source": HISTORICAL_LUNA_ALL_SOURCE,
        "benchmark_run_id": four_model_summary["benchmark_run_id"],
        "passed": luna["passed"],
        "total": luna["total"],
        "pass_rate": luna["pass_rate"],
        "provider_api_errors": luna["provider_api_errors"],
        "structured_output_errors": luna["structured_output_errors"],
        "estimated_cost_usd": luna["estimated_cost_usd"],
        "latency_ms": luna["latency_ms"],
        "stability": luna["stability"],
        "by_node": {task: four_model_summary["by_node"][task]["luna_all"] for task in TASKS},
        "hybrid_cost_reduction_percent": round(
            (luna["estimated_cost_usd"] - summary["cost"]["estimated_total_usd"])
            / luna["estimated_cost_usd"]
            * 100,
            6,
        ),
    }
    assert comparison["hybrid_cost_reduction_percent"] == 33.436154


def test_retained_price_snapshot_covers_every_frozen_benchmark_target():
    four_model = _load_json("evals/four_model_six_node_v1_2_benchmark.json")
    flash_luna = _load_json("evals/flash_luna_v1_2_benchmark.json")
    snapshot = _load_json("evals/four_model_six_node_v1_2_price_snapshot.json")

    frozen_targets = {
        (entry["provider"], entry["model"]) for entry in four_model["profiles"].values()
    }
    frozen_targets.update(
        (entry["provider"], entry["model"])
        for entry in flash_luna["profiles"]["flash_luna"]["task_targets"].values()
    )
    priced_targets = {(entry["provider"], entry["model"]) for entry in snapshot["prices"]}

    assert frozen_targets == priced_targets
