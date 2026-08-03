# AI-assisted development workflow

This project was built with two AI coding agents — [Codex](https://openai.com/codex/)
and [Claude Code](https://claude.com/claude-code) — working against a spec-driven
workflow that is committed to this repository. Architectural decisions and reviews were
made by a human; the agents worked inside explicit, version-controlled rules.

This document explains how that workflow is wired, because the workflow itself is part
of what this repository demonstrates.

## The six components

| Component | What it holds |
|---|---|
| [`CLAUDE.md`](../CLAUDE.md) | Durable project rules for Claude Code — the invariants an agent must not break (lazy external clients, side-effect-free imports, where the privacy lock lives, testing rules). |
| [`AGENTS.md`](../AGENTS.md) | The same durable rules for Codex, following the vendor-neutral `AGENTS.md` convention. |
| [`.claude/commands/`](../.claude/commands/) | 13 Claude Code slash commands covering planning, implementation, review, remediation, and maintenance. See its [README](../.claude/commands/README.md) for the full catalog. |
| [`.agents/skills/`](../.agents/skills/) | The same workflow as 13 Codex Skills, each a `SKILL.md` boundary plus a `references/workflow.md` procedure. |
| [`docs/roadmap/`](roadmap/README.md) | The three-stage workflow templates: **spec → plan → implementation report**. |
| [`docs/adr/`](adr/README.md) | 17 Architecture Decision Records — the durable output of the process, capturing context, trade-offs, and rejected alternatives. |

## Why the workflow exists twice

The two command sets are not a copy of each other. They are one workflow design
implemented against two agent platforms, because each platform loads and executes
instructions differently:

* **Rules are auto-loaded per platform.** Codex reads `AGENTS.md`; Claude Code reads
  `CLAUDE.md`. Neither reads the other's file. Collapsing them into one file with a
  pointer would demote the invariants from "already in context" to "the agent has to
  remember to go look" — not a trade worth making for rules like *imports must
  construct no client*.
* **The command formats differ.** A Claude Code command is a single Markdown file whose
  frontmatter declares an `allowed-tools` allowlist. A Codex Skill is a directory: a
  `SKILL.md` defining the input and execution boundary, and a `references/workflow.md`
  holding the detailed procedure.
* **Ten workflows are shared** — `eval-imple`, `imple-spec`, `new-function-spec`,
  `review-diff`, `apply-review-report`, and the five audits (`arch-review`,
  `security-review`, `failure-modes-review`, `test-coverage-review`,
  `docs-drift-review`). **Three exist as platform-specific mirrors**, because each one
  maintains its own platform's artifacts: `review-command` ↔ `review-skill`,
  `apply-command-review` ↔ `apply-skill-review`, `update-claude-md` ↔ `update-agents-md`.

In practice the two were used for different parts of the codebase — Codex primarily on
the React/TypeScript frontend, Claude Code primarily on the Python graph, server, and
the audit passes. Keeping the workflow portable across both is the point: the design is
in the taxonomy, not in one vendor's file format.

## The loop

The commands deliberately separate **deciding**, **building**, **reviewing**, and
**applying findings** into distinct steps, so that "should we build this?" is never
answered by the same pass that writes the code:

```text
Uncertain change  →  /eval-imple      (decide first; "no change" is a valid success)
Approved spec     →  /imple-spec      (build the approved scope only)
After changes     →  /review-diff     (pre-commit check)
Broad audit       →  /arch-review · /security-review · /failure-modes-review
                     /test-coverage-review · /docs-drift-review
Findings          →  /apply-review-report · /apply-command-review
Durable rules     →  /update-claude-md
```

Each review command owns exactly one axis and defers the others rather than duplicating
them — test-coverage gaps belong to `/test-coverage-review`, documentation accuracy to
`/docs-drift-review`, command-file correctness to `/review-command`.

## Rules are executable, not just prose

The part worth looking at: rules in `CLAUDE.md` and `AGENTS.md` are not left as advice
an agent may or may not follow. The important ones are enforced by tests, so a violation
fails CI rather than surviving review.

* **[`tests/graph/test_local_provider.py:277`](../tests/graph/test_local_provider.py#L277)** —
  `test_importing_the_project_constructs_no_external_client` spawns a subprocess with
  every `*_API_KEY` stripped from the environment, imports the project, and asserts that
  every lazy `@lru_cache` factory cache is still empty. This makes the "imports must be
  side-effect-free" rule executable: an eagerly constructed client that does not validate
  credentials at construction time (Chroma, a local Ollama client) would otherwise pass
  CI while breaking the invariant the whole mocked test strategy rests on.

* **[`tests/server/test_status_endpoint.py:326`](../tests/server/test_status_endpoint.py#L326)** —
  `test_server_modules_do_not_import_chains_or_nodes` asserts the `server/` import
  boundary that [ADR 016](adr/016-thin-web-application-layer.md), `structure.md` §14, and
  `CLAUDE.md` all state: the web layer imports the engine-facing modules only, never
  `graph.nodes.*` or the chain factories.

This is the mechanism that makes agent-assisted development safe to scale on a codebase:
the constraints live in tests, not in the reviewer's memory.

## Agent permission boundaries

Every command declares an explicit `allowed-tools` allowlist. No command is granted
unrestricted `Bash`:

* The five audit commands get `Read, Write, Glob, Grep` plus `Bash(git status:*)` and
  `Bash(date:*)` — they can read the repository and write a report, nothing else.
* Commands that may run tests are scoped per suite, e.g.
  `Bash(uv run pytest tests/node:*)`, not `Bash(uv run pytest:*)`.
* [`.claude/settings.json`](../.claude/settings.json) denies `Read(.env)` and `Edit(.env)`
  outright, so no agent in this project can read the real credentials file;
  `Edit(.env.example)` is allowed separately.

## What is published, and what is not

The **methods** are public; the **outputs** of running them on this codebase are not.
Specs, plans, implementation reports, and all review reports are written to
`docs/roadmap/<topic>/` and are gitignored — only `docs/roadmap/README.md` and the three
workflow templates are tracked.

This is deliberate. A `/security-review` report is a findings list about this
repository's own code; publishing it wholesale would be shipping an unreviewed issue
tracker. Findings that matter are resolved and then recorded where they belong — in an
ADR, in a test, or in [Current Limitations](../README.md#current-limitations).

## About `.mcp.json`

[`.mcp.json`](../.mcp.json) declares one read-only MCP server, the official LangChain
documentation endpoint (`https://docs.langchain.com/mcp`). It is used by
`/new-function-spec` and `/imple-spec` to check current LangChain and LangGraph APIs
instead of relying on model recall. [`.codex/config.toml`](../.codex/config.toml)
declares the same server for Codex.

Claude Code will ask you to approve it on first open. Declining is fine — it only removes
documentation lookup from those two commands; nothing else in the repository depends
on it.

## Reproducing the workflow

The commands are project-specific — they reference this repository's module layout, test
suites, and ADR conventions — but the structure is portable. To adapt it: keep one file
per platform as the source of durable rules, keep one axis per review command, keep
`allowed-tools` narrow, and make the rules you care about most into tests.
