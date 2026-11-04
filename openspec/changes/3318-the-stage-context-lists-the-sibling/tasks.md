# Tasks

## 1. Name the sibling trees of a created path

Reads: `src/devops_cli/roadmap/stage_paths.py`. Changes: `src/devops_cli/roadmap/stage_paths.py`, `tests/roadmap/test_roadmap_stage_paths.py`.

- [ ] 1.1 In `tests/roadmap/test_roadmap_stage_paths.py`, assert that `sibling_trees(".claude/skills/new-scaffold/SKILL.md", files)` returns `[".agents/skills/", ".kilocode/skills/"]` for a tree that holds `.agents/skills/openspec-x/SKILL.md` and `.kilocode/skills/openspec-y/SKILL.md`, returns no tree for a tree with one skill folder, leaves out `.agents/notes/SKILL.md`, and sorts `.agents/skills/` before `.kilocode/skills/`. Verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_paths.py` fails on the base
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_paths.py` fails on the base
- [ ] 1.2 Add `sibling_trees(path, files)` to `src/devops_cli/roadmap/stage_paths.py`. Replace the first segment and the directory before the file name with `*`, match each file with `PurePosixPath.full_match`, return the sorted first two segments of each match without the tree of `path`, and return no tree when `path` has fewer than three segments. Verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_paths.py` passes
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_paths.py` passes

## 2. Put the sibling trees in the stage context

Reads: `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/refine.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/stage_paths.py`, `docs/roadmap/stage.md`. Changes: `src/devops_cli/roadmap/stage.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_plan.py`, `docs/roadmap/stage.md`.

- [ ] 2.1 In `tests/roadmap/test_roadmap_stage_plan.py`, assert that the request context of an item whose body cites `.claude/skills/new-scaffold/SKILL.md` holds a `Sibling trees` section with `.agents/skills/` and `.kilocode/skills/` when the staged tree holds those trees, and holds no section when the staged tree holds one skill tree. Verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` fails on the base
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` fails on the base
- [ ] 2.2 In `src/devops_cli/roadmap/stage.py`, read `cited_paths(item.body)`, keep the paths that `self._tree` does not hold, call `sibling_trees` for each of them, and append the `Sibling trees` section to the value of `collect_context`. Add the heading and the instruction to `src/devops_cli/lang/en/messages.py`, and leave the section out when the list is empty. Verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` passes
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` passes
- [ ] 2.3 State the `Sibling trees` section and the rule that the plan covers each tree or gives a reason in `docs/roadmap/stage.md`
  - Verification: `uv run devops ci docs` passes

## 3. Ask the stage prompt to cover each tree

Reads: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`. Changes: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`.

- [ ] 3.1 Add one rule to `src/devops_cli/ai/tasks/roadmap_stage_change.md`: when the context holds a `Sibling trees` section, the plan creates the file in each listed tree, or states in `decisions` why one tree is enough. Assert the rule in `tests/roadmap/test_roadmap_stage_prompt_rules.py`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_prompt_rules.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
