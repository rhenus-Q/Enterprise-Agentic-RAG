# Detailed Workflow

This reference defines the project-specific procedure for applying accepted findings
from one Codex Skill review. The execution boundary in `../SKILL.md` is authoritative.

## Contents

- Safety constraints
- Resolve and validate the report
- Select findings
- Read the target Skill
- Apply focused fixes
- Validate the Skill
- Return the result

## Safety constraints

Modify only the reviewed Skill directory under `.agents/skills/<skill-name>/` and only
files directly required by accepted findings. Do not modify `AGENTS.md`, application
code, tests, evals, prompts, models, corpus documents, environment files, unrelated
Skills, review reports, or other roadmap artifacts.

Do not stage, commit, create branches, or switch branches. Do not run project tests,
evals, ingestion, the application, or commands requiring API keys.

## Resolve and validate the report

Require a report path under `docs/roadmap/skills-review/`. If input is empty, ask for
the exact path. Reject missing paths, paths outside that directory, and ambiguous search
results.

Read the report and extract:

- target `SKILL.md` path;
- verdict;
- Must fix findings;
- Should fix soon findings;
- Optional improvements;
- exact file and section evidence for each finding.

Require the target to resolve inside `.agents/skills/`. Stop if the report does not name
one unambiguous target Skill or if its evidence no longer matches the current files.

## Select findings

Apply Must fix and Should fix soon findings by default when they remain valid and fit the
user's request. Apply Optional improvements only when the user explicitly requests them.

Do not edit when:

- the verdict is Ready to use and there are no required findings;
- all findings are optional and optional work was not requested;
- the report is stale or contradicted by current repository evidence;
- a finding would expand scope beyond the target Skill;
- a finding would weaken safety or permission boundaries.

Report a no-change outcome as success when no justified edit remains.

## Read the target Skill

Read:

- target `SKILL.md`;
- target `agents/openai.yaml`, when present;
- every directly linked reference, script, or asset relevant to an accepted finding;
- `AGENTS.md` for repository-wide constraints.

Read peer Skills only when the report explicitly relies on a peer convention that must
be verified.

## Apply focused fixes

Make the smallest edits that resolve accepted findings. Preserve correct material and
avoid broad rewrites.

For `SKILL.md`:

- keep frontmatter limited to `name` and `description`;
- keep the directory and `name` aligned;
- put all trigger guidance in `description`;
- use imperative instructions in the body;
- keep the body below 500 lines;
- keep permission and file-write boundaries explicit;
- defer to current sandbox, approval, rules, and available tools.

For `agents/openai.yaml`:

- quote string values;
- keep UI metadata consistent with `SKILL.md`;
- ensure `default_prompt` explicitly mentions `$skill-name`;
- do not add icons, brand colors, dependencies, or policies without a real need.

For references and resources:

- maintain direct links from `SKILL.md`;
- add a contents section to references over 100 lines;
- remove duplicated or obsolete command-era instructions;
- do not introduce auxiliary README, changelog, or installation files.

Never add unsupported command-era frontmatter fields or tool allowlists. Never encode
permissions as though Skill prose could grant access.

## Validate the Skill

Perform static checks on every changed file. Run the skill creator's
`quick_validate.py` against the target Skill when the active approval policy permits
that local validation command. If it cannot be run, state that explicitly.

If Git metadata is available, inspect status and a diff restricted to the target Skill.
Confirm that no file outside the target directory changed. If the directory is not a Git
checkout, report that limitation and list changed files directly.

Do not forward-test the Skill when the test could modify repository files or require
additional approvals. Leave behavioral forward-testing for a separately authorized
validation phase.

## Return the result

Report:

- review report used;
- target Skill;
- findings applied and skipped;
- files changed;
- validation performed and omitted;
- confirmation that nothing outside the target Skill directory was modified.
