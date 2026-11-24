# Tasks

## 1. Render the generic kit rules when a checkout has no AGENTS.md

Kind: behavior. Reads: `src/devops_cli/ai/instruction_generator.py`, `src/devops_cli/templates/AGENTS.md.j2`, `tests/roadmap/implement/test_roadmap_implement_step_rules.py`, `tests/roadmap/implement/test_roadmap_implement_prompt.py`, `tests/roadmap/stage/test_roadmap_stage_measure.py`, `tests/roadmap/test_roadmap_step_rules.py`. Changes: `src/devops_cli/roadmap/step_rules.py`, `tests/roadmap/test_roadmap_step_rules.py`, `tests/roadmap/stage/test_roadmap_stage_measure.py`.
Adds: `GENERIC_RULES_HEADING`, `rules_section`, `generic_rules`

- [x] 1.1 Write the cases in `tests/roadmap/test_roadmap_step_rules.py` first and replace `test_a_checkout_without_agents_md_gets_no_section`, whose assert at `tests/roadmap/test_roadmap_step_rules.py:182:assert rules_sections(tmp_path, _group("tests/test_sample.py")) == []` expects the empty list: `test_a_checkout_without_agents_md_gets_the_generic_rules` for the scenario `A checkout with no AGENTS.md`, `test_a_checkout_without_agents_md_keeps_its_routed_sections` for the scenario `A checkout with no AGENTS.md and a routed document`, and `test_the_generic_rules_name_no_python_without_a_python_manifest` for the requirement `The generic rules name no toolchain that the checkout lacks` and its scenario `A checkout with no Python manifest`. In the same step update `tests/roadmap/stage/test_roadmap_stage_measure.py`, because a measure of a clone with no AGENTS.md now holds the generic section: subtract the rules sections in `_file_tokens`, and leave the generic section out of the difference that `tests/roadmap/stage/test_roadmap_stage_measure.py:100:assert after.tokens - before.tokens == count_tokens(rules) + count_tokens(testing)` asserts
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_step_rules.py tests/roadmap/stage/test_roadmap_stage_measure.py` fails on the base
- [x] 1.2 In `src/devops_cli/roadmap/step_rules.py` add `GENERIC_RULES_HEADING: Final[str] = "Generic rules of the kit (no AGENTS.md)"` and `rules_section(heading: str, text: str) -> str`, which returns the heading and the text cut to `CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS`. Add `generic_rules(source: Path) -> str`, which imports `generate_agents_md` and `parse_project_metadata` from `devops_cli.ai.instruction_generator` inside the function and returns the rendered rules. In `rules_sections`, build the first section with `rules_section(RULES_HEADING, agents.read_text(encoding="utf-8").strip())` when the checkout holds `AGENTS.md`, else with `rules_section(GENERIC_RULES_HEADING, generic_rules(source))`, and append the routed sections in both cases. In `tests/roadmap/stage/test_roadmap_stage_measure.py` subtract `sum(count_tokens(section) for section in rules_sections(clone, parsed))` in `_file_tokens`, with `parsed` from `parse_task_groups(group_text(1, group))`, and expect the before and after measure of `AGENTS.md` to differ by the rules and the routed sections less the generic section
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_step_rules.py tests/roadmap/stage/test_roadmap_stage_measure.py` passes

## 2. Regenerate the step message snapshot for the generic rules

Kind: other. Reads: `tests/support/implement_step.py`. Changes: `tests/roadmap/implement/__snapshots__/test_roadmap_implement_step.ambr`.

- [x] 2.1 Regenerate `tests/roadmap/implement/__snapshots__/test_roadmap_implement_step.ambr` with the snapshot update run of the test module that the verify names, because the checkout of `tests/support/implement_step.py` writes no `AGENTS.md` and the message of that step now starts with the generic rules section. Read the diff and keep every other entry of the file as it is
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_step.py` passes

## 3. Add the target AGENTS.md to the refine context

Kind: behavior. Reads: `src/devops_cli/roadmap/step_rules.py`, `tests/support/roadmap_stage.py`, `tests/support/roadmap_refine.py`, `tests/roadmap/refine/test_roadmap_refine_context.py`. Changes: `src/devops_cli/roadmap/refine/refine.py`, `tests/roadmap/refine/test_roadmap_refine_context.py`.

- [x] 3.1 Write the cases in `tests/roadmap/refine/test_roadmap_refine_context.py` first, on the real clone of the `stage_repo` fixture: `test_the_context_holds_the_agents_md_of_the_sha` for the scenario `A commit with an AGENTS.md` and the scenario `The rules section comes first`, `test_the_context_takes_the_agents_md_of_the_sha_and_not_the_working_tree` for the scenario `The working tree differs from the commit`, `test_a_large_agents_md_section_stays_under_the_cap` for the scenario `A 44,535-character AGENTS.md`, and `test_a_commit_without_agents_md_gets_the_generic_rules` for the scenario `A commit with no AGENTS.md`. Raise the budget of the three cases that assert text after the new section from 1000 to 4000 tokens, at `tests/roadmap/refine/test_roadmap_refine_context.py:62:ctx = collect_context(git_repo, sha, body, max_tokens=1000)`, at `tests/roadmap/refine/test_roadmap_refine_context.py:80:ctx = collect_context(git_repo, new_sha, "body", max_tokens=1000)` and at `tests/roadmap/refine/test_roadmap_refine_context.py:262:ctx = collect_context(git_repo, sha, body, max_tokens=1000)`, and keep the case that asserts the cut at 10 tokens
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_context.py` fails on the base
- [x] 3.2 In `collect_context` of `src/devops_cli/roadmap/refine/refine.py`, before the `CONTEXT.md` section, read `AGENTS.md` with `_read_git_file(source, sha, CONST_AGENTS_MD_FILENAME)`: append `rules_section(RULES_HEADING, text)` when the commit holds it, else `rules_section(GENERIC_RULES_HEADING, generic_rules(source))`. Import `RULES_HEADING`, `GENERIC_RULES_HEADING`, `rules_section` and `generic_rules` from `devops_cli.roadmap.step_rules`, and `CONST_AGENTS_MD_FILENAME` from `devops_cli.config.constants`. Keep the cut of the whole context to `max_tokens` at the end
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_context.py` passes

## 4. State the context rules and the stage eval replay score

Kind: other. Reads: `docs/roadmap/refine.md`. Changes: `docs/roadmap/refine.md`.

- [x] 4.1 Edit `docs/roadmap/refine.md` at the paragraph that starts `Refine uses the code and the documents of the repository.` to state that the context holds the `AGENTS.md` of the item's commit first, cut to `CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS`, and one section of the generic kit rules, under a heading that states that they are generic, when the commit holds none. Then run `uv run devops roadmap eval stage --replay` on the base commit and on the branch, write the score before and the score after into the pull request body, and stop the step when the after score is lower than the before score
  - Verification: `$ uv run devops roadmap eval stage --replay` passes
- [x] 4.2 Edit `docs/roadmap/refine.md` to state the rules section of the refine context: the `AGENTS.md` of the item's commit under the implement file cap, and the generic kit rules when the commit holds none. Update `tests/roadmap/test_roadmap_limit_classes.py`
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 3: A test: the refine context for a repository with `AGENTS.md` contains its first rule line, and stays within the token cap for a 44,535-character file.
- Group 1: A test: `rules_sections` for a checkout with no `AGENTS.md` returns 1 section with the generic rules, and none of them says "Python" when the checkout has no Python manifest.
- Group 4: The stage eval replay score is not lower (both numbers in the pull request).

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
