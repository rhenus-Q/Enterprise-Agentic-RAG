---
name: review-diff
description: Perform a focused, read-only pre-commit review of current working-tree changes. Summarize scope and changed files, report concrete bugs, regressions, security or privacy problems, and scope drift, assess validation evidence and commit readiness, and suggest precise Git commands when ready. Default to demo-level proportionality; do not demand new features, production hardening, broad validation, or unrelated cleanup. Apply strict release criteria only when explicitly requested.
---

# Review Diff

## Input and boundary

- Treat the user's request that invoked this Skill as the review focus.
- Infer an omitted focus from the current diff when the scope is unambiguous. Ask one
  concise question only when it cannot be inferred safely.
- Keep the review read-only. Do not modify files, implement fixes, stage changes,
  commit, create or switch branches, or run validation commands.
- Use as few tools as practical and honor the active sandbox, approval policy, and
  repository guidance.

## Review procedure

1. Read the repository-root `AGENTS.md`.
2. Inspect `git status --short`, unstaged and staged diff summaries, and changed-file
   lists. Review targeted unstaged and staged diffs rather than entire files whenever
   possible.
3. Read each relevant untracked file directly because it is absent from normal diffs,
   except for sensitive files covered below.
4. Classify changed files by purpose, such as application behavior, tests, evaluation,
   documentation, tooling, generated output, or unrelated change. Compare them with the
   requested scope.
5. Inspect only the surrounding source, tests, configuration, or referenced paths
   needed to verify the changed behavior.
6. Check unexpected changes to prompts, model names, corpus documents, graph behavior
   or routing, graph nodes, `stop_reason`, fallback policy, `.env` templates,
   `ingestion.py`, and `tests/chains/`. Report them only when they create a concrete
   risk or scope mismatch.
7. Use validation evidence already available in the conversation. Never claim a test,
   build, workflow, or hosted CI job passed without actual evidence.

## Sensitive files

- Never read `.env`, `.env.*`, `*.env`, `.envrc`, credentials, authentication state,
  API keys, provider settings, or files whose names suggest secrets, credentials,
  tokens, private keys, or certificates. Treat `.env.example` as readable only when
  repository guidance permits it.
- Assess an excluded file from its path and Git state only. If a secret-bearing file is
  untracked or staged, report it as a `❌` blocking finding and say it must be ignored or
  removed from the index before commit. Do not quote or summarize its contents.

## Review depth and finding quality

Primarily answer: **Can this code be committed safely?**

Prefer a small number of high-confidence findings backed by the current diff or
repository evidence. Every problem finding must identify an actionable location,
realistic trigger, impact, and whether it blocks commit.

Use the same finding markers as the Claude command:

- `✅` for safe or expected behavior that materially supports the judgment.
- `⚠️` for a real but non-blocking issue or a required minor check.
- `❌` for a serious correctness, security, reliability, data-loss, compatibility,
  secret-exposure, scope, or other commit-blocking problem.

Do not impose a numeric cap on useful positive findings, but keep them concise and do
not narrate routine facts. Clearly label optional polish as optional plain text, not as
`⚠️`, and keep it separate from required action.

Do not:

- Propose unrelated features, future architecture, or unnecessary redesigns.
- Invent edge cases without realistic evidence in the current diff.
- Turn naming, wording, formatting, harmless duplicate validation, optional refactors,
  or other style preferences into warnings.
- Require exhaustive validation when targeted checks cover the changed scope.
- Produce long lists of optional improvements.

Mention a prior finding only when it is still present in the current working tree,
materially affects commit safety, and directly relates to the current diff or validation
result. Do not carry forward fixed findings, unrelated history, style preferences, or
optional future improvements.

## Strict mode

Read and follow [the strict workflow](references/strict-workflow.md) only when the user
explicitly requests a strict review, production-readiness review, release gate, or an
equivalent exhaustive assessment. Strict mode still follows the evidence and
proportionality rules above.

## Commit readiness

Use exactly one Claude-compatible outcome:

- `Ready to commit`
- `Ready after minor check`
- `Not ready`
- `Needs clarification`

Use `Ready after minor check` only when no code fix is known to be required but one
small, directly relevant validation or confirmation remains. Optional polish never
changes readiness.

## Validation guidance

Recommend the smallest checks that match the changed scope:

- Frontend-only: relevant frontend tests, typecheck, and production build.
- Python-only: targeted pytest plus directly relevant lint or type checks.
- Documentation-only: no executable suite unless the documentation controls executable
  behavior.
- CI workflow: local validation where possible, while stating that hosted execution
  requires a push.

Do not recommend full-repository validation when targeted checks are sufficient. Never
run ingestion, `tests/chains/`, real-service/API commands, or full behavioral evaluation
under this read-only Skill.

## Output

Use these headings in this order:

### Review summary

- `Scope:`
- `Risk level:`
- `Commit readiness:` using exactly one allowed value above.

### Changed files

List changed files grouped by purpose. Collapse purely mechanical files when practical.

### Findings

List important findings using `✅`, `⚠️`, and `❌`. Separate serious blockers, minor
non-blocking issues, and optional polish. If there are no serious problems, say so
directly and keep the section brief.

### Validation

List checks already evidenced and the smallest checks still recommended. State that the
Skill did not run validation.

### Commit recommendation

- For `Ready to commit`, provide an explicit `git add` command limited to intended
  files and a concise `git commit` command.
- For `Ready after minor check`, state the check first and provide commands to use only
  after it passes.
- Prefer explicit paths. Suggest `git add .` only when the diff is very small and every
  changed file is clearly intended. Use `git add -A -- <paths>` for deletions or
  renames.
- For `Not ready` or `Needs clarification`, omit commit commands and explain what must
  be resolved.
- Present commands as suggestions only; do not execute them.

### Confirmations

Always include this matrix:

| Area | Changed? |
| --- | --- |
| Prompts | Yes / No |
| Model names | Yes / No |
| Corpus documents | Yes / No |
| `.env` / `.env.example` | Yes / No |
| Graph behavior | Yes / No |
| Full eval results | Yes / No |

Briefly explain any `Yes` that matters to commit safety. Do not expand `No` rows into
repetitive prose.
