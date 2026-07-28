# Strict Review Workflow

Use this workflow only when the user explicitly requests a strict review, production
readiness assessment, release gate, or equivalent exhaustive review. The execution
boundary and finding standard in `SKILL.md` remain authoritative.

## 1. Inspect repository state

Inspect:

```powershell
git status --short
git diff --stat
git diff --name-only
git diff --cached --stat
git diff --cached --name-only
```

Review targeted unstaged and staged diffs instead of reading every full file:

```powershell
git diff -- <file>
git diff --cached -- <file>
```

Read every relevant untracked file because it is absent from `git diff`. Follow the
sensitive-file boundary in `SKILL.md`.

## 2. Confirm scope

Compare the changed files with the user's intended change. Flag unrelated edits,
generated artifacts, accidental formatting churn, and unexpected changes to sensitive
areas only when they create a concrete scope or safety problem.

## 3. Assess release risk

Review changed behavior for:

- Correctness and regression risk.
- Security, privacy, secret handling, and external egress.
- Graph routing, retry limits, fallback policy, and `stop_reason` semantics.
- Prompt, model, corpus, ingestion, provider, or index compatibility changes.
- Backward compatibility at interfaces touched by the diff.
- Failure handling at external boundaries touched by the diff.

Keep findings tied to the current diff. Do not propose unrelated features or broader
architecture work.

## 4. Assess validation evidence

Use validation evidence already present in the conversation. When evidence is absent,
recommend only checks that directly exercise the changed behavior. Recommend broader
test or evaluation sets only when the diff itself is broad enough to require them.

Never run validation commands under this Skill. Never recommend real-service tests,
ingestion, or full behavioral evaluation unless they are necessary for the explicit
release-readiness question and the repository guidance permits them.

## 5. Give the release judgment

Choose one:

- `Ready to commit`
- `Ready after targeted validation`
- `Not ready`
- `Needs clarification`

Base the judgment on concrete findings, scope correctness, and available validation
evidence. Do not block a commit solely for optional hardening or generic best practices.

Use the output structure in `SKILL.md`. Strict mode may include additional concrete
release-risk findings, but it must not restore a fixed confirmations matrix or list
unrelated checks. When the judgment is `Ready to commit`, provide explicit staging and
commit commands limited to the reviewed files. Use `git add -A -- <paths>` for
deletions or renames, and never default to `git add .`. Present the commands as
suggestions only; do not execute them.
