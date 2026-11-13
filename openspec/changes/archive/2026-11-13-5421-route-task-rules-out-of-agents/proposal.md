# Proposal

## Why

Every agent session loads `AGENTS.md` in full, and the roadmap jobs read it too (#5421). It had 6,499 characters against the cap of 6,500 (`CONST_AGENTS_MD_MAX_CHARS`). So each session paid for rules that most tasks do not need, and no new rule could go in. Most of the text was a rule for some tasks only, a detail, or a copy of a sentence that another document already owns. The owner asked on 2026-11-13 to route that text to the documents that own it.

## What Changes

- `AGENTS.md` keeps only the rules that every task needs, the safety rules and the "Where to look" table. It has 4,220 characters, 35.1 percent fewer than before. The description line goes, because `README.md` holds it.
- Each sentence that leaves `AGENTS.md` has one home. Most homes already held the sentence: `CONTRIBUTING.md` (alpha status, pull request title and body, hard-wrap rule), `docs/SDLC.md` (rebase before each push, OpenSpec plan and archive, no milestone or priority, `devops pr monitor`, review threads, oldest pull request first, no Copilot review, required checks), `docs/TESTING.md` (fail-to-pass), `openspec/config.yaml` (`## Feasibility`, the cost of a build), `docs/ROUTINE_TASKS.md` (a `devops` command that fails or warns), `RELEASE_CYCLE.md` (release steps) and `SECURITY.md` (the hostname forms, the registry form and the mount path form).
- The safety rules stay inline. Rule 10 keeps the whole private-data list (secret, gitignored file, internal hostname, private address or registry, device path) and the placeholders `example.com`, RFC 5737 and `<storage-node>`, because the implement step reads `AGENTS.md` and not `SECURITY.md` for a group under `k8s/**` or `tf/**`.
- Rule 13, the decision model rule, leaves the list. Rule 7 keeps "Run one `devops ai` call at a time, only when no file or deterministic check can answer" for every call, and links the `ask-jev` skill, which owns the choice of the model kind. The old rule 14 is now rule 13. It keeps "each necessary fact" in front of its examples.
- Rule 2 keeps the case of an item that newer issues or code replace: close it as not planned. The triage line of `docs/SDLC.md` names the same cases.
- Rule 11 asks to comment on the open issue of a problem first, and to file one only when none is open.
- `SECURITY.md` rule 8 names `example.com` for a domain. The naming table of `CONTRIBUTING.md` gives the form `<path>.bak-<YYYYMMDD-HHMMSS>` of the copy that an agent makes before it edits a file outside the workspace.
- `RELEASE_CYCLE.md` owns the rule that agents change the release workflow only through ordinary pull requests, and no longer cites `AGENTS.md` for it.
- `openspec/config.yaml` names the cost of a build with the words of the stage prompt: the tokens to build, keep and fix it.
- `CONST_AGENTS_MD_MAX_CHARS` goes from 6,500 to 4,500, which is 6.6 percent above the new size and above the 4,206 characters that the template renders for devops-cli. The budget test bound goes to 4,500 too. The constant also caps the model answer of `devops ai agents` for every target repository, so that cap goes from 6,500 to 4,500 too.
- The tests read each moved sentence where it lives now: the fail-to-pass test reads `docs/TESTING.md`, and the shared phrases of the stage prompt pair with `SECURITY.md` and `openspec/config.yaml`. New tests hold the safety rules inline, the superseded-item case of rule 2, and the model-call limit and skill link of rule 7.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `agent-instructions`: The agent instructions separate the two model kinds. AGENTS.md holds only the rules that every task needs (added). AGENTS.md keeps the safety rules inline (added).

## Impact

- Documents: `AGENTS.md`, `SECURITY.md`, `CONTRIBUTING.md`, `RELEASE_CYCLE.md`, `docs/SDLC.md`, `openspec/config.yaml`, the comment of `.github/workflows/fail-to-pass.yml`.
- Code: `src/devops_cli/config/constants.py` (`CONST_AGENTS_MD_MAX_CHARS`).
- Tests: `tests/invariants/test_agents_md.py`, `tests/ci/test_fail_to_pass.py`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`, `tests/roadmap/stage/test_roadmap_stage_cost_units.py` (docstring).
- `devops ai agents` replaces a model answer over 4,500 characters with the template, which renders 3,827 to 4,206 characters. Its template, its system prompt and the pointer stubs do not change. The template still holds detail that `AGENTS.md` moved out; a trim of the template is a separate item.
- Rules 1 to 12 keep their numbers and titles, so the citations of rule 3, rule 5, rule 6, rule 8 and rule 11 stay true. Only the citation of rule 4 in `fail-to-pass.yml` and of rule 13 in the spec change.
- No conflict with #5419: its pull request changed only `src/devops_cli/ai/tasks/style_ste100.md` and the living spec of `agent-instructions`, and rule 9 keeps its link to the style file.

## Feasibility

- `git show origin/main:AGENTS.md` at 192ca691c has 6,499 characters (6,501 bytes); `CONST_AGENTS_MD_MAX_CHARS` is 6,500 (`src/devops_cli/config/constants.py`).
- I read each target section and found the moved sentence there before the change, for example `docs/SDLC.md` "Copilot Reviews", "Sequential Pull Request Processing Queue" and "Current Branch at Every Push"; `docs/TESTING.md` "A fix pull request cites its `devops ci fail-to-pass --base <ref>` run"; `CONTRIBUTING.md` "The Title Is the Changelog Line" and "Line Breaks Belong to Source Files"; `docs/ROUTINE_TASKS.md` tenet 6.
- `generate_agents_md(parse_project_metadata(REPO_ROOT))` renders 4,206 characters, so the cap of 4,500 needs no template change.
- The rule-title test (`_rule_drift`) compares titles only. The 12 template titles stay in `AGENTS.md`, and only "Write prose in ASD-STE100" stays in the devops-cli list.
- `step_rules.py` `ROUTES` reads five "When you" cells verbatim; those cells and their links do not change. `rules_sections` gives every implement step all of `AGENTS.md`, and `SECURITY.md` only for a group under `src/devops_cli/security/**`, so the private-data rule stays whole in `AGENTS.md`.
- `tests/roadmap/implement/test_roadmap_implement_prompt.py` keeps the rules of the project out of the step prompt (`DROPPED_RULES`, #3097), and needs `.data/agent/scratch/` in `AGENTS.md`.

## Existing Tool Considered

No tool covers this. It is a document change, held by the existing invariant tests of `AGENTS.md`. The cost was about 300,000 tokens and 3 hours of elapsed time. The change deletes no internal code.
