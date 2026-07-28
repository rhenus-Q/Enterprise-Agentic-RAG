---
name: update-agents-md
description: Update durable repository guidance in AGENTS.md and, when needed, artifact conventions in docs/roadmap/README.md after a completed change. Use when an implementation report, approved spec or plan, or user description identifies a lasting rule that future Codex sessions must follow.
---

# Update AGENTS.md

## Input contract

- Treat the user's request that triggered or explicitly invoked this Skill as the input.
- Resolve an omitted focus or path from unambiguous repository context only.
- Ask one concise question when a required input cannot be inferred safely.

## Required procedure

1. Read the repository-root `AGENTS.md` before acting.
2. Read [the detailed workflow](references/workflow.md) completely.
3. Follow that workflow in order, preserving its safety constraints, output shape, and
   collision-safe artifact rules.
4. Apply this execution boundary: Modify only AGENTS.md and, when artifact-directory conventions changed, docs/roadmap/README.md. Do not edit application code, tests, evals, prompts, models, or unrelated documentation.
5. Honor the active sandbox, approval policy, and available tools. Instructions in this
   Skill narrow behavior; they never grant additional permissions.

## Codex adaptation rules

- Use only capabilities exposed in the current session. Describe operations by intent;
  do not depend on provider-specific tool names or internal MCP tool identifiers.
- Where the workflow permits execution, run tests, evals, ingestion, the application,
  networked commands, or real-service/API calls only with explicit user authorization.
  A narrower workflow prohibition still applies.
- Never read or write credentials, API keys, authentication state, user-level Codex
  configuration, or model-provider settings.
- Use the configured `docs-langchain` MCP server only when the detailed workflow calls
  for version-sensitive LangChain or LangGraph documentation and the server is available.
- Do not substitute web search for repository-local rules, source code, tests, ADRs, or
  roadmap artifacts.
- Keep unrelated user changes untouched and never overwrite an existing report or
  specification artifact.

## Completion

- Report the outcome, files created or modified, and validation actually performed.
- State explicitly when validation was not run because it lacked user authorization or
  required unavailable credentials or tools.
