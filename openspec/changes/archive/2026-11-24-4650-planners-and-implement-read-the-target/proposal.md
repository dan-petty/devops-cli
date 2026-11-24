# Proposal

## Why

The planner reads CONTEXT.md and the first five ADRs, and the implement step reads no rules at all when the checkout holds no `AGENTS.md`, so the rules of the target never reach the model in five of six repositories (#4650). This change puts the target `AGENTS.md`, cut to the implement file cap, into the refine context, and gives the generic kit rules when the file is absent.

## What Changes

- `src/devops_cli/roadmap/step_rules.py`: add `GENERIC_RULES_HEADING`, `rules_section` and `generic_rules`, so one builder keeps the cap and the heading of every rules section, and `rules_sections` returns one section of the generic kit rules first when the checkout holds no `AGENTS.md`.
- `tests/roadmap/test_roadmap_step_rules.py` and `tests/roadmap/stage/test_roadmap_stage_measure.py` hold the cases of the fallback and of the measure that counts it, with the rules sections left out of the file tokens.
- `tests/roadmap/implement/__snapshots__/test_roadmap_implement_step.ambr` is regenerated, because the step message of a checkout with no `AGENTS.md` now starts with the generic rules section.
- `src/devops_cli/roadmap/refine/refine.py`: `collect_context` adds the `AGENTS.md` of the item's `sha` first, before `CONTEXT.md` and the ADRs, or the generic rules when the commit holds none.
- `tests/roadmap/refine/test_roadmap_refine_context.py` holds the cases of the sha, of the cap and of the generic rules, and raises the budget of the cases that read text after the new section.
- `docs/roadmap/refine.md` states the rules section of the context, and the pull request body states the stage eval replay score before and after.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-step/inputs`: A checkout with no AGENTS.md gets the generic rules, The generic rules name no toolchain that the checkout lacks
- `roadmap-refine/context`: The refine context holds the AGENTS.md of the item's commit, The rules section comes from the item's commit and not the working tree, The refine context gets the generic rules when the commit holds none

## Impact

- Code: `src/devops_cli/roadmap/step_rules.py`, `src/devops_cli/roadmap/refine/refine.py`
- Documents: `docs/roadmap/refine.md`
- Tests: `tests/roadmap/test_roadmap_step_rules.py`, `tests/roadmap/stage/test_roadmap_stage_measure.py`, `tests/roadmap/implement/__snapshots__/test_roadmap_implement_step.ambr`, `tests/roadmap/refine/test_roadmap_refine_context.py`

## Feasibility

- The probe line The path `AGENTS.md` is a file of the staging commit. confirms the rules file that the issue reads, and the probe line The path `CONTEXT.md` is a file of the staging commit. confirms the optional project file that it keeps.
- `read_file` of `src/devops_cli/roadmap/refine/refine.py` lines 1050 to 1100 showed `collect_context` reading `CONTEXT.md` at the item's sha (`src/devops_cli/roadmap/refine/refine.py:1060:ctx = _read_git_file(source, sha, "CONTEXT.md")`) and the first five ADRs in name order (`src/devops_cli/roadmap/refine/refine.py:1068:for adr_path in [p for p in adr_items if p][:5]:`), so the premise of the issue holds at the staged commit and its line numbers moved from the numbers of the body.
- `read_file` of `src/devops_cli/roadmap/step_rules.py` showed the empty list of a checkout with no rules (`src/devops_cli/roadmap/step_rules.py:139:return []`), the heading that the step already uses (`src/devops_cli/roadmap/step_rules.py:30:RULES_HEADING: Final[str] = "Rules of the repository (AGENTS.md)"`) and the cap of one section (`src/devops_cli/roadmap/step_rules.py:141:agents.read_text(encoding="utf-8").strip(), CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS`), so a checkout with no `AGENTS.md` gives the implement step no rules today.
- The cap is `CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS`, 8000, at `src/devops_cli/config/constants.py:3730:CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS: Final[int] = 8000`, and the plan gives that bound no new name.
- `read_file` of `src/devops_cli/ai/instruction_generator.py` lines 160 to 275 showed the renderer that #4641 delivered: `src/devops_cli/ai/instruction_generator.py:177:resolved_path = repo_path.resolve()` is the first line of `parse_project_metadata`, which takes a folder, and `src/devops_cli/ai/instruction_generator.py:249:tasks = dict(CONST_AGENTS_MD_ROUTES)` is the first line of `generate_agents_md`, which renders `AGENTS.md.j2` with the detected toolchain.
- `read_issue` of #4641 reported it closed (completed), with the comment `Released in v0.114.0`, so the renderer is delivered before this work and blocks nothing.
- `read_file` of `src/devops_cli/templates/AGENTS.md.j2` showed the toolchain line only under `{% if toolchains %}` (`src/devops_cli/templates/AGENTS.md.j2:4:{% if toolchains %}`) and the Python sentence only under `{% if python %}` (`src/devops_cli/templates/AGENTS.md.j2:17:{% if python %} A fix pull request shows that its new tests fail on the base with `devops ci fail-to-pass --base <ref>`.{% endif %}`), so a checkout with no manifest gets no line that says Python.
- `references` for `rules_section(` answered that no line of the commit holds it, so `rules_section`, `GENERIC_RULES_HEADING` and `generic_rules` are names that group 1 adds.
- The `missing_path` finding is a defect: `tests/roadmap/implement/test_roadmap_implement_step.py:175:assert inputs.message == snapshot` compares the whole message with `tests/roadmap/implement/__snapshots__/test_roadmap_implement_step.ambr:4:# Item #1: Make the sample shout`, and the checkout of `tests/support/implement_step.py` writes no `AGENTS.md` before its one commit (`tests/support/implement_step.py:98:git(checkout, "commit", "-q", "-m", "init")`). Group 2 regenerates that snapshot and verifies it with that test module.
- The `other` finding is a defect: `tests/roadmap/stage/test_roadmap_stage_measure.py:100:assert after.tokens - before.tokens == count_tokens(rules) + count_tokens(testing)` measures a clone with no `AGENTS.md` before it writes one, and that measure now holds the generic section. Group 1 subtracts the rules sections in `_file_tokens` and leaves the generic section out of that difference.
- Precondition of `collect_context`: a checkout of the repository, because its reads go through git at a sha.
- Precondition of `_read_git_file`: a checkout of the repository, because it reads a file of a commit there.
- Precondition of `rules_sections`: a checkout of the repository, because it reads `AGENTS.md` and the routed documents there.
- Precondition of `parse_project_metadata`: a checkout of the repository, because it reads the manifests and the pre-push hooks there. `generate_agents_md` takes metadata and needs no checkout, no client and no network.
- Precondition of `measure_groups`: a checkout of the repository, because it packs the named files there.
- Precondition of `uv run devops roadmap eval stage --replay`: a checkout of the repository, because `load_cases` and the replay read the recorded cases there (`src/devops_cli/commands/roadmap_eval_stage.py:254:replay: Annotated[bool, typer.Option("--replay", help=HELP.roadmap.eval_stage_replay)] = False,`). It calls no model, no client and no network.
- The test commands are `uv run devops ci test <paths>`: `uv`, `devops` and `pytest` are runner tools of the image, no program is NOT_IN_RUNNER, the cases reach no network, no cluster and no real scanner, and the pod sets `readOnlyRootFilesystem: true`, `allowPrivilegeEscalation: false`, `capabilities.drop: ALL`, `runAsNonRoot: true` and `seccompProfile: RuntimeDefault`.
- `uv run devops roadmap eval stage --replay` runs with the runner tools `uv` and `devops` of the image, names no NOT_IN_RUNNER program, and its failure class is a nonzero exit when a gate refuses a good plan or stops refusing a known-bad plan, with the same pod settings.
- The first checks against the real system are `uv run devops ci test tests/roadmap/test_roadmap_step_rules.py tests/roadmap/stage/test_roadmap_stage_measure.py`, then `uv run devops ci test tests/roadmap/implement/test_roadmap_implement_step.py`, then `uv run devops ci test tests/roadmap/refine/test_roadmap_refine_context.py`, then `uv run devops roadmap eval stage --replay` on the base commit and on the branch.
- Not checked: the count of repositories without `AGENTS.md`, the 44,535 characters of the target file, and the score of `uv run devops roadmap eval stage --replay` before and after. The tests write a 44,535-character file of their own, and group 4 runs the replay and writes both numbers into the pull request body.

## Existing Tool Considered

No open, maintained tool or library covers the need: `AGENTS.md` is a convention file, and the work is this repository's own `collect_context` and `rules_sections`, which already share the section builder of the implement step. No tool reads the target `AGENTS.md` at an item's commit or renders the kit rules for a checkout without one. Written cost to build, keep and fix that code instead: 150k tokens and 2 hours of elapsed time, about 40 lines and 4 tests. The change deletes no internal code.

## Dependencies

- #4641: the generic rules render with the `generate_agents_md` and `parse_project_metadata` that #4641 delivered, and `read_issue` reports it closed (completed) in release v0.114.0, so it is delivered before this work.
