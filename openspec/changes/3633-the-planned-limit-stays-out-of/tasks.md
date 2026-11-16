# Tasks

## 1. Say in the queue line and prove in a test that refine takes New items at the limit

Kind: behavior. Reads: `src/devops_cli/roadmap/inbox.py`, `src/devops_cli/roadmap/refine/refine.py`, `tests/support/roadmap_refine.py`, `tests/support/config.py`, `tests/support/fakes/model.py`, `tests/roadmap/test_roadmap_inbox.py`, `tests/roadmap/refine/test_roadmap_refine_selection.py`, `tests/roadmap/test_roadmap_limit_classes.py`, `tests/roadmap/implement/test_roadmap_implement_amend.py`, `docs/roadmap/inbox.md`. Changes: `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_inbox.py`, `tests/roadmap/refine/test_roadmap_refine_selection.py`, `docs/roadmap/inbox.md`.

- [x] 1.1 `tests/roadmap/test_roadmap_inbox.py::test_the_inbox_states_the_planned_limit_when_it_holds` fails first on the new sentence of the queue line, and `tests/roadmap/refine/test_roadmap_refine_selection.py::test_the_planned_limit_does_not_stop_a_round_from_setting_a_new_item_ready` fails first on the scenario "The limit is 1 with 50 Planned items": with roadmap.stage.planned_limit at 1, 50 Planned items and one New item, one round makes one model call and sets the item Ready. The inbox case also asserts the scenario "The line says that refine goes on" and that the line names roadmap.stage.planned_limit and P0-Critical or P1-High, and the refine case holds the requirement "The Planned limit does not stop a refine round"
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_inbox.py tests/roadmap/refine/test_roadmap_refine_selection.py` fails on the base
- [x] 1.2 In `src/devops_cli/lang/en/messages.py`, add the sentence "A refine round still takes New items." to the `queue` subject of `MESSAGES.roadmap.inbox_subjects` after the sentence that names the priorities, and leave the format placeholders as they are. `tests/roadmap/implement/test_roadmap_implement_amend.py` imports `MESSAGES` and needs no edit, so the catalog keeps its contract. Add the assertion of the new sentence to the case `test_the_inbox_states_the_planned_limit_when_it_holds` in `tests/roadmap/test_roadmap_inbox.py`, beside the assertion at `tests/roadmap/test_roadmap_inbox.py:495:assert "The stage job plans only items with the priority P0-Critical or P1-High." in text`. Add the case `test_the_planned_limit_does_not_stop_a_round_from_setting_a_new_item_ready` to `tests/roadmap/refine/test_roadmap_refine_selection.py` in the shape of the round at `tests/roadmap/refine/test_roadmap_refine_selection.py:323:apply_refine(store, plan_refine(store, repo=REPO, source=git_repo))`: take the `git_repo`, `store`, `model_fake` and `config` fixtures from `tests/support/roadmap_refine.py`, `tests/support/fakes/model.py` and `tests/support/config.py`, answer the model with the ready proposal `{"existing_tool": NO_OPEN_TOOL, "problem_statement": "The item needs a design.", "acceptance_criteria": [CRITERION_JSON]}`, call `config(roadmap={"stage": {"planned_limit": 1}})`, `store.seed_visibility(is_private=True)`, seed 50 items with `seed_item(store, "Planned", "P2-Medium")` and one with `seed_item(store, "New", "P3-Low")`, run `apply_refine(store, plan_refine(store, repo=REPO, source=git_repo, limit=1))`, and assert one model call, the New item's number in the prompt, and its status Ready. `tests/roadmap/test_roadmap_limit_classes.py` keeps its table, because the new case adds no roadmap limit
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_inbox.py tests/roadmap/refine/test_roadmap_refine_selection.py` passes
- [x] 1.3 Edit `docs/roadmap/inbox.md` so the queue item says that a refine round still takes New items, and run `uv run devops docs generate`
  - Verification: `$ uv run devops ci docs` passes

## 2. Name the stage job only in the explain help and its pages

Kind: other. Reads: `src/devops_cli/lang/en/help.py`, `docs/CLI_REFERENCE.md`, `docs/commands/roadmap.md`, `docs/roadmap/stage.md`, `docs/ENV_VARS.md`. Changes: `src/devops_cli/lang/en/help.py`, `docs/CLI_REFERENCE.md`, `docs/commands/roadmap.md`, `docs/roadmap/stage.md`.

- [ ] 2.1 In `src/devops_cli/lang/en/help.py`, change the `explain` text so the setting is named as a rule of the stage job only: replace the fragment at `src/devops_cli/lang/en/help.py:1929:roadmap.stage.planned_limit), and the limit of a run.` so the sentence reads that the setting roadmap.stage.planned_limit is a rule of the stage job only. Regenerate `docs/CLI_REFERENCE.md` and `docs/commands/roadmap.md` with `uv run devops docs generate`, so `docs/commands/roadmap.md:238:and the setting roadmap.stage.planned_limit), and the limit of a run.` and `docs/CLI_REFERENCE.md:315:and the setting roadmap.stage.planned_limit), and the limit of a run.` carry the new words and no hand edit. Add the sentence "The limit applies to the stage job only." to `docs/roadmap/stage.md` beside `docs/roadmap/stage.md:35:The limit does not apply to the filing of issues.`
  - Verification: `$ uv run devops ci docs` passes
- [ ] 2.2 Edit `docs/roadmap/stage.md`, and regenerate `docs/CLI_REFERENCE.md` and `docs/commands/roadmap.md` with `uv run devops docs generate`, and run `uv run devops docs generate`
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 1: A test: with the limit at 1 and 50 Planned items, refine selects a New item and sets it to Ready, as with no Planned items.
- Group 1: `openspec/specs/roadmap-refine/spec.md` holds the requirement.
- Group 2: The help text, `README.md` and `docs/commands/roadmap.md` say that the setting applies to the stage job only.
- Group 1: The inbox queue line says that refine goes on at the limit.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
