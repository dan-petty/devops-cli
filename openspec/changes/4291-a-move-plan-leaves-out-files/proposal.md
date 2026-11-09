# Proposal: #4291

## Why

The move-reference gate of the stage job treats a plan as a move of a module when it is no move, and it asks a plan to edit files that nobody edits (#4291). `moved_modules` in `src/devops_cli/roadmap/stage/stage_change.py` calls a Python module moved when a task group lists it in `changes` and the group creates any file, a test included. The job then greps the whole staged commit for the path and the dotted name of that module, and the gate refuses each hit that no group changes. The hits include `CHANGELOG.md`, which only release-please writes, and the change folders of other items, which are records. Four items failed with this gate in 24 hours, with 2248 sentences of the shape "The move plan leaves out `CHANGELOG.md`." The failure text of #3599 is 88 000 characters long, so the model cannot answer it.

## What Changes

- Derive a moved module from the same module created in another place: a created module of the same name, or a created module under the sub-package that the name prefix gives. A group that changes a module and creates only a test, a document or a module of another name moves nothing.
- Leave out of the gate each probed file of class `tool-owned` or `record` in `CONST_DOCS_INVENTORY`.
- The change carries a spec delta because it changes which plans the stage job refuses.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: A move needs the module in another place, and the probe leaves out the files of a tool and the records

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_change.py`
- Tests: `tests/roadmap/stage/test_roadmap_stage_move_references.py`

## Feasibility

- The cause is in the code: `moved_modules` in `src/devops_cli/roadmap/stage/stage_change.py` skipped only a group with no `creates`, and `_move_reference_problems` refused every probed path that no group changed.
- The stage job logs of the last 24 hours (Loki, `service_name=roadmap-service`) hold the refusals. Word for word, from #3599: "The move plan leaves out `CHANGELOG.md`. Add a task group that changes it or mark it unchanged with a reason. The move plan leaves out `openspec/changes/3253-map-all-issue-requirements-to-a/proposal.md`."
- The inventory of the documents states the class of each file: `CHANGELOG.md` is `tool-owned`, and `openspec/changes/**/*.md` is `record` ("history, never rewritten to match later code") in `CONST_DOCS_INVENTORY` of `src/devops_cli/config/constants.py`. `explicit_classes` of `src/devops_cli/docs/inventory.py` reads it.
- First check against the real system: `uv run devops roadmap eval stage --replay`, which must keep its verdict on every case, the case `3412-a-move-plan-leaves-a-test-reference` included.
- Second check: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_move_references.py tests/roadmap/stage/test_roadmap_stage_plan.py`.

## Existing Tool Considered

`explicit_classes` of `src/devops_cli/docs/inventory.py` already classes the files, and `PurePosixPath.full_match` reads the globs, so the change adds no parser and no list of paths. The cost is about 25k tokens to build, 3k tokens to keep and 1 hour. The change deletes the rule "any group with a created file moves each module it changes".
