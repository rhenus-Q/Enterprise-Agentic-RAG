"""Subprocess guarantee for `evals/run_eval.py --validate-only`.

CLAUDE.md and structure.md §9 promise that dataset validation "must stay
keys-free and dependency-free: it returns before the graph is imported *and*
before startup preflight runs". The preflight half is already covered in-process
(test_validate_only_never_runs_preflight, test_validate_only_bypasses_preflight_
with_an_invalid_flag). This module covers the other half, and it does so in a
fresh interpreter because both claims are about what a *cold* process does:
checking the parent's sys.modules proves nothing once pytest has already
imported the graph for some other suite.

Two things are asserted:

1. The CLI exits 0 with every provider credential scrubbed from the environment
   — including the ones tests/conftest.py's load_dotenv() call pulls out of the
   repository's .env and into os.environ, which the child would otherwise
   inherit.
2. The CLI never imports the graph runtime, enforced by a guarded
   builtins.__import__ installed in the child before run_eval.py executes.

The guard uses an allowlist rather than "no module named graph": run_eval.py
already imports graph.config and graph.consts at module scope (both are pure —
graph/consts.py imports nothing, graph/config.py imports only os), and that is
the documented shape of the guarantee. Everything else under `graph`, plus
`ingestion` and `main`, is blocked, so hoisting `from graph.engine import ...`
to module scope fails here immediately.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUN_EVAL = PROJECT_ROOT / "evals" / "run_eval.py"

# Modules under `graph` that dataset validation is allowed to touch.
ALLOWED_GRAPH_MODULES = ("graph", "graph.config", "graph.consts")

# Root modules that pull in the graph runtime, a provider client, or preflight.
FORBIDDEN_ROOT_MODULES = ("ingestion", "main")

# Cleared from the child's environment so "it works without keys" is a real
# claim and not an accident of the developer's .env.
CREDENTIAL_ENV_VARS = (
    "OPENAI_API_KEY",
    "OPENAI_API_BASE",
    "OPENAI_BASE_URL",
    "OPENAI_ORGANIZATION",
    "TAVILY_API_KEY",
    "ANTHROPIC_API_KEY",
    "LANGCHAIN_API_KEY",
    "LANGSMITH_API_KEY",
)

# Marker prefixes so a guard trip is distinguishable from an unrelated crash.
IMPORT_GUARD_MARKER = "BLOCKED-IMPORT:"
CREDENTIAL_MARKER = "LEAKED-CREDENTIAL:"

_CHILD_PROGRAM_BODY = """
import builtins
import os
import runpy
import sys

for _name in CREDENTIAL_ENV_VARS:
    if os.environ.get(_name):
        raise AssertionError(CREDENTIAL_MARKER + _name)

_real_import = builtins.__import__


def _guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
    root = name.split(".")[0]
    blocked = (root == "graph" and name not in ALLOWED_GRAPH_MODULES) or (
        root in FORBIDDEN_ROOT_MODULES
    )
    if blocked:
        raise AssertionError(IMPORT_GUARD_MARKER + name)
    return _real_import(name, globals, locals, fromlist, level)


builtins.__import__ = _guarded_import

_run_eval_path = sys.argv[1]
sys.argv = [_run_eval_path, "--validate-only"]
runpy.run_path(_run_eval_path, run_name="__main__")
"""


def _child_program(allowed_graph_modules: tuple[str, ...]) -> str:
    """Prefix the guard body with its configuration as plain literals."""

    preamble = (
        f"ALLOWED_GRAPH_MODULES = {allowed_graph_modules!r}\n"
        f"FORBIDDEN_ROOT_MODULES = {FORBIDDEN_ROOT_MODULES!r}\n"
        f"CREDENTIAL_ENV_VARS = {CREDENTIAL_ENV_VARS!r}\n"
        f"IMPORT_GUARD_MARKER = {IMPORT_GUARD_MARKER!r}\n"
        f"CREDENTIAL_MARKER = {CREDENTIAL_MARKER!r}\n"
    )
    return preamble + _CHILD_PROGRAM_BODY


def _scrubbed_environment() -> dict[str, str]:
    environment = dict(os.environ)
    for name in CREDENTIAL_ENV_VARS:
        environment.pop(name, None)
    # Never let an ambient tracing configuration turn this into a network call.
    environment["LANGCHAIN_TRACING_V2"] = "false"
    environment["LANGSMITH_TRACING"] = "false"
    return environment


def _run_validate_only(allowed_graph_modules: tuple[str, ...]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", _child_program(allowed_graph_modules), str(RUN_EVAL)],
        cwd=str(PROJECT_ROOT),
        env=_scrubbed_environment(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )


def _diagnostics(completed: subprocess.CompletedProcess) -> str:
    return (
        f"\nexit code: {completed.returncode}"
        f"\n--- stdout ---\n{completed.stdout}"
        f"\n--- stderr ---\n{completed.stderr}"
    )


def test_validate_only_succeeds_without_credentials_and_without_the_graph() -> None:
    completed = _run_validate_only(ALLOWED_GRAPH_MODULES)

    assert completed.returncode == 0, (
        "evals/run_eval.py --validate-only must exit 0 with no provider credentials "
        f"and without importing the graph runtime.{_diagnostics(completed)}"
    )
    assert "Dataset OK" in completed.stdout, (
        f"Expected the dataset validation summary on stdout.{_diagnostics(completed)}"
    )
    assert IMPORT_GUARD_MARKER not in completed.stderr, _diagnostics(completed)
    assert CREDENTIAL_MARKER not in completed.stderr, _diagnostics(completed)


@pytest.mark.parametrize("blocked_module", ["graph.config", "graph.consts"])
def test_the_import_guard_actually_fires(blocked_module: str) -> None:
    # Without this, a guard that silently failed to install would make the test
    # above pass for the wrong reason. Removing an allowed module must break it.
    narrowed = tuple(name for name in ALLOWED_GRAPH_MODULES if name != blocked_module)

    completed = _run_validate_only(narrowed)

    assert completed.returncode != 0, (
        f"The child import guard did not block {blocked_module}.{_diagnostics(completed)}"
    )
    assert IMPORT_GUARD_MARKER + blocked_module in completed.stderr, _diagnostics(completed)


def test_the_scrubbed_environment_carries_no_provider_credentials() -> None:
    environment = _scrubbed_environment()

    assert [name for name in CREDENTIAL_ENV_VARS if name in environment] == []
