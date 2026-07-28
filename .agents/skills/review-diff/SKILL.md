---
name: review-diff
description: Perform a focused, read-only review of current working-tree changes for concrete bugs, regressions, security or privacy problems, and scope drift. Use after files have changed and the user wants a proportional pre-commit assessment. Default to demo-level review; do not demand new features, production hardening, broad validation, or unrelated cleanup. Apply strict release criteria only when the user explicitly requests them.
---

# Review Diff

## Scope

1. Read the repository-root `AGENTS.md`.
2. Infer the intended change from the user's request and the changed files.
3. Inspect git status and the relevant diffs, including relevant untracked files.
4. Review changed lines plus only the minimum surrounding context needed.
5. Check whether the demonstrated path remains correct; do not assess general production
   readiness unless the user asks for it.

Ask one concise question only when the intended scope cannot be inferred safely.

## Finding standard

Report a finding only when all of these are true:

- The current diff introduces or exposes the problem.
- A concrete trigger or failure path can be described.
- The impact is a wrong result, crash, security or privacy issue, data loss, or clear
  deviation from the requested scope.
- The finding identifies an actionable file location.

Use `BLOCK` only for a material correctness, safety, privacy, or scope problem. Use
`WARN` for a concrete but non-blocking regression or validation gap tied directly to
changed behavior. Omit speculative improvements.

Do not:

- Recommend new features or unrelated behavior.
- Treat generic best practices as findings.
- Require production hardening, observability, refactoring, extra configuration,
  additional documentation, or test infrastructure for a demo.
- Treat missing tests or documentation as a finding by itself.
- Turn hypothetical future concerns into commit blockers.

## Strict mode

Read and follow [the strict workflow](references/strict-workflow.md) only when the user
explicitly requests a strict review, production-readiness review, release gate, or an
equivalent exhaustive assessment. Do not apply that workflow by default.

## Execution boundary

- Keep the review read-only. Do not modify files, stage changes, commit, or run tests,
  evals, linters, type checks, compilation, ingestion, or the application.
- Honor the active sandbox, approval policy, and repository guidance.
- Never read or write credentials, API keys, authentication state, user-level Codex
  configuration, or model-provider settings.
- Use repository-local rules, source, tests, ADRs, and roadmap artifacts as the
  authoritative evidence.

## Output

- Lead with the overall result.
- List only concrete findings, ordered by severity, with exact file locations and
  failure scenarios.
- Recommend at most the smallest validation directly relevant to the changed behavior.
- If no concrete issues are found, say so plainly.
- State that validation was not run because the Skill is read-only.
- When the reviewed changes are ready to commit, always provide an explicit `git add`
  command limited to the intended files and a concise `git commit` command. Use
  `git add -A -- <paths>` when the commit includes deletions or renames; never default
  to `git add .`.
- When the changes are not ready, omit commit commands and state the concrete blocker.
- Present commit commands as suggestions only; do not execute them.
- Do not add a fixed confirmation checklist.
