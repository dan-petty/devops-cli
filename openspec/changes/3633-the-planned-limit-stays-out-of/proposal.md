# Proposal

## Why

The owner stated on 2026-11-05 that the planning threshold must not stop an item from going from New to Ready. The code holds that rule, but the stage requirement names only the filing of issues, and the explain help, its generated pages and the inbox queue line read as if the limit held every job. A reader and a later change can therefore move the limit into refine, and nothing fails (#3633).

## What Changes

- Add the requirement "The Planned limit does not stop a refine round" to the capability `roadmap-refine/selection`.
- Add the case `test_the_planned_limit_does_not_stop_a_round_from_setting_a_new_item_ready` to `tests/roadmap/refine/test_roadmap_refine_selection.py`: with the setting at 1 and 50 Planned items, one round sets the New backlog item Ready with one model call.
- Say in the queue subject of `MESSAGES.roadmap.inbox_subjects` in `src/devops_cli/lang/en/messages.py` that a refine round still takes New items.
- Add the same rule to the queue item of `docs/roadmap/inbox.md`.
- Change the `roadmap-inbox` requirement "The inbox states when the Planned limit holds" so the line says that refine goes on.
- Say in the `explain` help of `src/devops_cli/lang/en/help.py` that the setting is a rule of the stage job only, and regenerate `docs/CLI_REFERENCE.md` and `docs/commands/roadmap.md` from it.
- Add the stage-only sentence to `docs/roadmap/stage.md`.
- Edit no `README.md` line, because it names no such setting.
- The change carries a spec delta because the explain help and the inbox queue line are observable `devops` messages and the refine rule is new in the living spec.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-refine/selection`: The Planned limit does not stop a refine round
- `roadmap-inbox`: The inbox states when the Planned limit holds

## Impact

- Code: `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`
- Documents: `docs/roadmap/inbox.md`, `docs/CLI_REFERENCE.md`, `docs/commands/roadmap.md`, `docs/roadmap/stage.md`
- Tests: `tests/roadmap/test_roadmap_inbox.py`, `tests/roadmap/refine/test_roadmap_refine_selection.py`

## Feasibility

- The premise holds: `references` for `planned_limit` answered "References to 'planned_limit': files 50, lines 140." and it names no `src/devops_cli/roadmap/refine/refine.py`, so refine reads none of the setting.
- The probes show that the issue's bare paths are shorthand for the package: "The path `roadmap/stage.py` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/ai/spend/stage.py`, `src/devops_cli/roadmap/stage/stage.py`."
- The probes show that the setting is a key and no path: "The path `roadmap.stage.planned_limit` is no file of the staging commit. No commit in the history deleted or renamed it."
- `read_file` of `src/devops_cli/lang/en/help.py` lines 1900 to 1940 shows the setting inside the rules of every job: `src/devops_cli/lang/en/help.py:1929:roadmap.stage.planned_limit), and the limit of a run.`
- `read_file` of `docs/commands/roadmap.md` lines 225 to 250 shows the generated page carries the same sentence: `docs/commands/roadmap.md:238:and the setting roadmap.stage.planned_limit), and the limit of a run.`
- `read_file` of `docs/CLI_REFERENCE.md` lines 300 to 330 shows the command matrix carries it too: `docs/CLI_REFERENCE.md:315:and the setting roadmap.stage.planned_limit), and the limit of a run.`
- `read_file` of `src/devops_cli/lang/en/messages.py` lines 5430 to 5470 shows the queue subject at line 5449 and not near line 3636: `src/devops_cli/lang/en/messages.py:5451:The stage job plans only items with the priority {priorities}.`
- `read_file` of `docs/roadmap/inbox.md` lines 18 to 32 shows the queue item: `docs/roadmap/inbox.md:27:The stage job then plans only items with the priority`.
- `read_file` of `docs/roadmap/stage.md` lines 25 to 42 shows the stage page names the stage job and adds only the filing rule: `docs/roadmap/stage.md:35:The limit does not apply to the filing of issues.`
- `read_file` of `openspec/specs/roadmap-stage/selection/spec.md` lines 150 to 180 shows the stage rule stays true: `openspec/specs/roadmap-stage/selection/spec.md:172:The limit SHALL NOT apply to the filing of issues.`
- `read_file` of `openspec/specs/roadmap-explain/spec.md` lines 100 to 125 shows the explain rule already scoped to the stage job: `openspec/specs/roadmap-explain/spec.md:112:For the stage job, `devops roadmap explain <issue>` SHALL print `no` for an item that the limit`.
- `read_file` of `tests/roadmap/refine/test_roadmap_refine_selection.py` lines 1 to 60 and 255 to 345 shows the round pattern that the new case follows: `tests/roadmap/refine/test_roadmap_refine_selection.py:323:apply_refine(store, plan_refine(store, repo=REPO, source=git_repo))`.
- `read_file` of `tests/roadmap/test_roadmap_inbox.py` lines 475 to 505 shows the case that the new sentence updates: `tests/roadmap/test_roadmap_inbox.py:495:assert "The stage job plans only items with the priority P0-Critical or P1-High." in text`.
- `read_file` of `tests/roadmap/refine/test_roadmap_refine_trust.py` lines 296 to 320 shows the only refine test that names the setting passes it to the inbox: `tests/roadmap/refine/test_roadmap_refine_trust.py:309:inbox = read_inbox(store, repo=REPO, now=_NOW, planned_limit=20, draft_days=7, wait_days=7)`.
- `read_file` of `tests/support/roadmap_refine.py` lines 263 to 332 shows the seed helper and the store, gateway and model fixtures: `tests/support/roadmap_refine.py:263:def seed_item(`.
- `read_file` of `tests/support/config.py` lines 1 to 60 shows the fixture that writes the setting and resets the cache: `tests/support/config.py:25:def config(isolate_devops_cli_config: Path) -> Callable[..., Path]:`.
- `read_file` of `tests/roadmap/implement/test_roadmap_implement_amend.py` lines 1 to 60 shows a test of the message catalog: `tests/roadmap/implement/test_roadmap_implement_amend.py:5:from devops_cli.lang.en.messages import MESSAGES`.
- `read_file` of `tests/roadmap/test_roadmap_limit_classes.py` lines 1 to 70 shows the table that each new limit joins: `tests/roadmap/test_roadmap_limit_classes.py:44:CLASSES: Final = frozenset({"raised", "guard", "window", "setting", "kept", "other"})`.
- `list_files` of `openspec/specs/roadmap-refine` shows only the nested folders `alternatives`, `context`, `deferred-parts`, `investigation`, `proposal`, `review`, `selection`, `waits` and `writes`, and no `spec.md`, so the requirement goes into `roadmap-refine/selection`.
- `list_files` of `openspec/specs/roadmap-stage` shows the same: nested folders and no `spec.md`.
- `read_spec` of `roadmap-inbox` gives the requirement "The inbox states when the Planned limit holds" with the scenarios "At the limit" and "Under the limit", and the modified text keeps both.
- The inputs hold the text of `openspec/specs/roadmap-refine/selection/spec.md`, whose requirements include "Only the limit stops a refine round", and `capabilities` lists no flat `roadmap-refine`, so the new requirement joins that nested capability.
- The issue's `README.md` premise is false: `references` for `planned_limit` lists no `README.md` among its 50 files, so the plan edits no README line.
- The issue cites `openspec/specs/roadmap-stage/spec.md:1682` and `openspec/specs/roadmap-refine/spec.md`; the probes did not check those paths, `list_files` shows no `spec.md` in either area, and the living rules sit in the nested folders, so the plan writes in `roadmap-refine/selection` and `roadmap-inbox`.
- `plan_refine` needs a checkout of the repository in its `source` argument and a client of GitHub in its `store` argument: the new case passes the `git_repo` fixture and the fake store of `tests/support/roadmap_refine.py`.
- `apply_refine` needs the same client of GitHub, and the model call needs no network: the `model_fake` fixture answers it inside the test.
- The verify commands introduce no new program: `uv run devops ci test` and `uv run devops ci docs` are rows of the gate, `uv` and `devops` are runner tools of the image, and no tool of NOT_IN_RUNNER is called.
- The needed failure classes are `test`, `lint` and `types` for `uv run devops ci test` and `ci_infra` for `uv run devops ci docs`, each with an action in the failure taxonomy, and the pod keeps `readOnlyRootFilesystem: true` and `runAsNonRoot: true`.
- The first checks of the implementation against the real system are `uv run devops ci test tests/roadmap/refine/test_roadmap_refine_selection.py`, `uv run devops ci test tests/roadmap/test_roadmap_inbox.py` and `uv run devops ci docs`.

## Existing Tool Considered

OpenSpec holds the living requirement and pytest runs the tests, and the project already uses both. Neither covers the project-specific rule or the text edits, so the change adds one requirement, two tests and text edits and builds no tool.

## Dependencies

- PR #5786 changes `docs/commands/roadmap.md`, `src/devops_cli/lang/en/help.py` and `src/devops_cli/lang/en/messages.py`, the files of groups 1 and 2, so the second pull request rebases.
- PR #5816 changes `docs/ROADMAP_WORKFLOW.md`, `openspec/specs/roadmap-stage/selection/spec.md` and `src/devops_cli/lang/en/messages.py`; this change edits `src/devops_cli/lang/en/messages.py` only and leaves `docs/ROADMAP_WORKFLOW.md` and the stage selection spec as they are, so the two pull requests share one file.
