# Proposal

## Why

Issue #3097: the agent of the implement step works from the short prompt `src/devops_cli/ai/tasks/roadmap_implement_step.md`. A person in the devcontainer works from `AGENTS.md`, which holds the rules of every task and routes each kind of task to the document that owns it. The step does not read `AGENTS.md`. A rule changes in `AGENTS.md`, and the step does not follow it until someone copies it into the prompt.

The prompt has already drifted. It says "nesting of 5 or less", and `CONTRIBUTING.md` says that Ruff caps nesting at 4 (`PLR1702`, `max-nested-blocks = 4`). The live runs of 2026-11-01 broke rule 12 (scratch files in the checkout root), removed a pinned test, and wrote prose and tests that CI rejects (rules 4, 5 and 9). The tracker is #3027.

## What Changes

- The user message of a step holds the text of `AGENTS.md` of the checkout, verbatim, under the heading "Rules of the repository (AGENTS.md)". A checkout without that file gets no such section.
- A new module `src/devops_cli/roadmap/step_rules.py` holds `ROUTES`, one small table: a path pattern, the document, the sections of the document, and the "When you" cell of the row of `AGENTS.md` that routes to the document. For each group, the step adds the named sections of each routed document, when a path that the group names matches a pattern. A group that changes `tests/` gets `docs/TESTING.md`. A group that changes `src/` gets `ARCHITECTURE.md` and `CONTRIBUTING.md`. A group that changes `k8s/` gets `k8s/README.md`. A group that changes only `docs/` or a manifest gets no test document. A fix step names no path, so it gets `AGENTS.md` only.
- A test reads the "Where to look" table of `AGENTS.md` with markdown-it and fails when a route names a row that the table lacks, a document that the row does not link, a document that is missing, or a section that the document lacks.
- A routed section is cut by heading, with `section_text`, which moves from `implement_step.py` to `step_files.py` so that both modules use it. A whole document is too large: `docs/TESTING.md` is about 12,000 tokens and `k8s/README.md` about 45,000. The sections of one document stay under `CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS`, and a longer text is cut to that cap as a file is.
- The stage job measures a group with the same function (`step_rules.rules_sections`), so the measure counts `AGENTS.md` and the routed sections. The step budget `roadmap.stage.step_tokens` holds for the real message.
- The prompt keeps what is specific to the runner: the order of work, the tick rule, the shell table, the tool names, the output cap, the kept tests and the scratch rule with the note on stray files. It drops the rules that `AGENTS.md` and the routed documents own. It says where the rules are. A test fails when a `.data/` path in the prompt differs from the paths in `AGENTS.md`, and when the prompt restates a dropped rule.
- Observable behavior changes (the message of a step and the measure of the stage job), so the change carries two spec deltas.
- The change fits one pull request.

The change does not move a rule out of `AGENTS.md` and does not change `AGENTS.md`. It does not count the step prompt in the stage measure. That gap exists today and is out of scope.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-step`: modifies "The inputs of a step are fixed" and adds "The routes name the documents of a group".
- `roadmap-stage`: modifies "The job measures each task group".

## Impact

- Code: `src/devops_cli/roadmap/step_rules.py` (new), `src/devops_cli/roadmap/step_files.py`, `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/config/settings.py` (the text of `step_tokens`).
- Prompt: `src/devops_cli/ai/tasks/roadmap_implement_step.md`.
- Documents: `README.md`, `docs/CLI_REFERENCE.md`, `docs/commands/roadmap.md` and `docs/ENV_VARS.md` (generated), and the two specs (by archive).
- Tests: `tests/roadmap/test_roadmap_step_rules.py` (new), `tests/roadmap/test_roadmap_implement_step_rules.py` (new), `tests/roadmap/test_roadmap_implement_prompt.py`, `tests/roadmap/test_roadmap_stage_measure.py`.

## Feasibility

- `wc -c AGENTS.md` gives 6,499 characters, and `count_tokens` gives 1,667 tokens. The cap of 6,500 characters is a test (`tests/invariants/test_agents_md_claims.py`), so the added text per step is at most about 1,700 tokens.
- `uv run python` with markdown-it (`MarkdownIt("commonmark").enable("table")`) reads the 14 rows of the "Where to look" table of `AGENTS.md`: a "When you" cell, and the link targets of the "Read" cell. So the drift test needs no hand-made parser. `PurePosixPath.full_match` of Python 3.14 matches `tests/a/b.py` with `tests/**`, and does not match `tests`.
- `count_tokens` of the routed documents: `docs/TESTING.md` 12,048, `ARCHITECTURE.md` 4,697, `CONTRIBUTING.md` 4,831, `SECURITY.md` 2,902, `docs/ROADMAP_WORKFLOW.md` 5,433, `k8s/README.md` about 44,800. A whole document would break the step budget of 40,000 tokens, so the routes name sections.
- `git grep -n "step_files\|measure_groups" -- src` shows that `stage_change.measure_groups` counts the item, the change folder, the group and the packed named files, and nothing from the checkout rules. So without a change the budget would count too little.
- The prompt says "nesting of 5 or less". `CONTRIBUTING.md` line 14 says 4. The prompt restates a rule and has drifted.

## Existing Tool Considered

The change uses the markdown-it parser that the project already uses (`step_files.MARKDOWN`) for the sections and for the test of the table, `PurePosixPath.full_match` of the standard library for the patterns, and `count_tokens` and `truncate_to_token_limit` for the cap. No open tool routes the rules of a repository to an agent by the path of a change. `AGENTS.md` is the open convention for the rules, and the change reads it as the convention says. The new code is one table and about 60 lines. The cost to build is about 90,000 tokens, to keep it about 5,000 tokens a year, and to fix it about 15,000 tokens. It takes one working day. The change deletes the rule bullets of the prompt that `AGENTS.md` owns, and the copy of `section_text` in `implement_step.py`.
