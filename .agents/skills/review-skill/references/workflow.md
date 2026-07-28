# Detailed Workflow

This reference defines the project-specific procedure for reviewing one repository
Codex Skill. The execution boundary in `../SKILL.md` is authoritative.

## Contents

- Safety constraints
- Resolve the target Skill
- Read focused context
- Select a collision-safe report path
- Review metadata and discovery
- Review progressive disclosure and resources
- Review safety, permissions, and project fit
- Write the report
- Return the summary

## Safety constraints

Treat this as a review-only task. Do not modify the target Skill, `AGENTS.md`,
application code, tests, evals, prompts, models, corpus documents, environment files,
or existing roadmap artifacts. Write exactly one new report under
`docs/roadmap/skills-review/`.

Do not run tests, evals, ingestion, the application, or commands requiring API keys.
Do not stage, commit, create branches, or switch branches.

## Resolve the target Skill

Require one of these input forms:

- `.agents/skills/<skill-name>/SKILL.md`
- `.agents/skills/<skill-name>/`
- `$<skill-name>`
- `<skill-name>`

If input is empty, ask for a Skill name or path.

Normalize the input as follows:

1. Trim whitespace and surrounding backticks.
2. Remove one leading `$` from a bare Skill name.
3. If input is an explicit path, resolve it only under `.agents/skills/`.
4. If the path names a Skill directory, append `SKILL.md`.
5. If input is a bare name, resolve `.agents/skills/<skill-name>/SKILL.md`.
6. Reject paths outside `.agents/skills/`.

If there is no exact match, search only immediate Skill directories for close names.
Use a single unambiguous match; otherwise list candidates and ask for the exact name.

## Read focused context

Read:

- `AGENTS.md`
- the target `SKILL.md`
- the target `agents/openai.yaml`, when present
- every resource linked directly from the target `SKILL.md`

Read a small number of peer `SKILL.md` files only when comparison is necessary. Prefer
peers with similar responsibilities and avoid broad repository scans.

If Git metadata is available, inspect working-tree status without changing it. If the
directory is not a Git checkout, record that limitation and continue the static review.

## Select a collision-safe report path

Obtain the current local date from the environment immediately before the first report
write. Do not infer it from model knowledge or copy it from existing reports.

Use:

`docs/roadmap/skills-review/<YYYY-MM-DD>-<skill-name>-skill-review.md`

If it exists, append `-2`, `-3`, and so on before `.md`. Never overwrite an existing
report. Create the report directory only when needed.

## Review metadata and discovery

Verify that:

- YAML frontmatter has standard `---` delimiters.
- Frontmatter contains exactly `name` and `description`.
- `name` uses lowercase letters, digits, and hyphens, is under 64 characters, and
  matches the Skill directory name.
- `description` says what the Skill does and when it should trigger.
- Trigger language is specific enough to avoid accidental activation and broad enough
  to match intended requests.
- Invocation examples use `$skill-name`, not legacy slash-command syntax.

When `agents/openai.yaml` exists, verify that:

- string values are quoted;
- `display_name` is human-readable;
- `short_description` is concise and accurate;
- `default_prompt` is one short example sentence that explicitly mentions
  `$skill-name`;
- optional dependencies and policies, when present, match the actual Skill.

Do not require unsupported command-era frontmatter or tool allowlists. Their presence
in `SKILL.md` is a defect.

## Review progressive disclosure and resources

Verify that:

- `SKILL.md` contains only the essential workflow and stays below 500 lines;
- detailed material is moved to directly linked `references/` files when useful;
- reference links resolve and do not require deep reference chains;
- reference files over 100 lines include a contents section;
- scripts exist only when deterministic repeated execution warrants them;
- assets are output resources rather than instruction documents;
- the Skill does not add an unnecessary README, changelog, installation guide, or
  other auxiliary documentation;
- information is not duplicated across `SKILL.md` and references.

## Review safety, permissions, and project fit

Verify that the Skill:

- states exactly which files it may create or modify;
- protects application code, tests, evals, prompts, models, corpus data, secrets,
  routing, state schema, and existing reports when outside its scope;
- handles missing input, missing files, ambiguous matches, dirty working trees, and
  output collisions;
- never treats prose as a permission grant;
- explicitly defers to current sandbox, approval, rules, and available-tool policy;
- does not embed obsolete internal tool identifiers;
- uses the configured `docs-langchain` MCP server only for version-sensitive
  LangChain or LangGraph documentation;
- follows `AGENTS.md` and the repository's roadmap artifact conventions;
- produces a useful result without reading unrelated files or wasting context.

For write-capable Skills, check that validation remains proportional to the change and
does not silently authorize tests, evals, network access, or real-service calls.

## Write the report

Use this structure:

```markdown
# Codex Skill Review

Status: Review

Date: <YYYY-MM-DD>

Target Skill: `<target SKILL.md path>`

Report file: `<selected report path>`

## 1. Executive summary

Verdict: Ready to use / Ready after minor fixes / Not ready

## 2. Files reviewed

## 3. Metadata and discovery review

## 4. Progressive-disclosure and resource review

## 5. Scope, safety, and permission review

## 6. Input and output behavior review

## 7. Project fit and consistency review

## 8. Problems found

For each problem: issue, evidence, impact, severity, and recommended fix.

## 9. Recommended fixes

### Must fix

### Should fix soon

### Optional improvements

## 10. Final verdict
```

Write only the selected report. Do not edit the Skill being reviewed.

## Return the summary

Return the report path, target Skill path, verdict, and up to three top issues. Do not
repeat the full report unless the user asks.
