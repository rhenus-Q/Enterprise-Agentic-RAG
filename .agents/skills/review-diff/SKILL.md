---
name: review-diff
description: Perform a focused, read-only pre-commit review of current working-tree changes. Summarize scope and changed files, report concrete bugs, regressions, security or privacy problems, and scope drift, assess validation evidence and commit readiness, and suggest precise Git commands when ready. Default to demo-level proportionality; do not demand new features, production hardening, broad validation, or unrelated cleanup. Apply strict release criteria only when explicitly requested.
---

# Review Diff

## Review procedure

1. Read the repository-root `AGENTS.md`.
2. Inspect `git status --short`, unstaged and staged diff summaries, and changed-file
   lists. Review targeted unstaged and staged diffs for files that need closer analysis.
3. Read each relevant untracked file directly because it is absent from normal diffs.
4. Infer the intended scope from the user's request and the changed files. Group the
   files by purpose.
5. Review changed lines plus only the minimum surrounding context needed to verify
   behavior, configuration, test intent, or referenced paths.
6. Use validation evidence already present in the conversation. Do not claim a command
   passed unless its result is available.

Ask one concise question only when the intended scope cannot be inferred safely.

## Sensitive files

- Never read credentials, authentication state, API keys, provider settings, or files
  whose names suggest secrets, tokens, private keys, or certificates. Treat
  `.env.example` as readable only when repository guidance permits it.
- If a secret-bearing or authentication file is untracked or staged, report a `BLOCK`
  using its path and Git state only. Do not quote or summarize its contents.
- Do not suggest staging a sensitive file until the user has explicitly established
  that it is a safe repository template or configuration artifact.

## Finding standard

Report a finding only when the current diff introduces or exposes a concrete problem
with an actionable file location and a describable trigger or failure path.

- Use `BLOCK` for a material correctness, safety, privacy, data-loss, secret-exposure,
  or scope problem.
- Use `WARN` for a concrete non-blocking regression or a validation gap that directly
  prevents confidence in changed observable behavior.
- Use at most three `PASS` notes, and only when they establish a non-obvious fact needed
  for commit readiness, such as a CI-referenced lockfile being tracked.
- Omit speculative improvements and routine praise.

Do not:

- Recommend new features or unrelated behavior.
- Treat generic best practices as findings.
- Require production hardening, observability, refactoring, extra configuration,
  additional documentation, or test infrastructure for a demo.
- Treat missing tests or documentation as a finding by itself.
- Turn hypothetical future concerns into commit blockers.
- Carry findings from an earlier review forward unless the current diff still contains
  the concrete problem.
- Enumerate every sensitive area that the diff did not touch.

## Strict mode

Read and follow [the strict workflow](references/strict-workflow.md) only when the user
explicitly requests a strict review, production-readiness review, release gate, or an
equivalent exhaustive assessment. Do not apply that workflow by default.

## Commit readiness

Choose one outcome:

- `Ready to commit`: no concrete blocker remains and the intended scope is clear.
  Optional or already-covered validation does not block this outcome.
- `Ready after targeted validation`: correctness depends on one or more specific,
  directly relevant checks whose results are unavailable.
- `Not ready`: at least one concrete blocking problem exists.
- `Needs clarification`: the intended scope or ownership of changed files cannot be
  inferred safely.

## Execution boundary

- Keep the review read-only. Do not modify files, stage changes, commit, or run tests,
  evals, linters, type checks, compilation, ingestion, or the application.
- Honor the active sandbox, approval policy, and repository guidance.
- Never read or write credentials, API keys, authentication state, user-level Codex
  configuration, or model-provider settings.
- Use repository-local rules, source, tests, ADRs, and roadmap artifacts as the
  authoritative evidence.

## Output

Use this compact structure:

### Review summary

- State scope, risk level, and commit-readiness outcome.

### Changed files

- Group files by purpose and describe each group briefly.
- Collapse purely mechanical files into one line when practical.

### Findings

- Order `BLOCK`, `WARN`, then the limited `PASS` notes.
- Give exact file locations, trigger conditions, and impact for problems.
- If there are no concrete problems, say so plainly.

### Validation

- State what validation is already evidenced and what was not run because the Skill is
  read-only.
- Recommend no more than three commands, and only when they directly exercise the
  changed behavior. Do not list unrelated checks merely to say they are unnecessary.

### Commit recommendation

- For `Ready to commit`, always provide an explicit `git add` command limited to the
  intended files and a concise `git commit` command.
- Use `git add -A -- <paths>` when the commit includes deletions or renames. Never
  default to `git add .`.
- For any other outcome, omit commit commands and state the concrete blocker or
  required targeted validation.
- Present commands as suggestions only; do not execute them.

Do not add a fixed confirmations matrix.
