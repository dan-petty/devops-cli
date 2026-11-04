# Proposal

## Why

The implement job runs the docs step and the archive step in every target repository (#3484). The step `uv run devops docs generate --sync-readme` fails in a repository that is not devops-cli: the installed copy finds its docs folder from the package file and writes to `/app/docs`, which the Job mounts read-only. In one day, 53 Jobs on two target repositories stopped there and delivered nothing. The rule `digest` cleared each stop for each new runner image, and the same stop came back. A correct docs path would be wrong too, as it would write the command reference of devops-cli into a target repository.

## What Changes

- The job runs the docs step and the archive step only where the default branch of the target declares them in `.devops/roadmap.toml`, with `[implement.steps]` and the keys `docs` and `archive`. The job reads the file from the default branch with git, as `trusted_config` reads the hooks, so an edit of the checkout adds or removes no step. A default branch with no file declares no step. A file that is not valid stops the item with the path of the file in the reason.
- One predicate gates the docs step for `_finish_change` and for `_scoped_rounds`. The archive step uses the same declaration.
- The comment of the job on the pull request names each step that it skipped.
- A target that skips the archive step is ready with an unarchived change: the readiness decision of the job asks for the archive only where the target declares it.
- The failure class `read_only_path` has the default action `wait`. The rule reads `Read-only file system` and `EROFS`. The action is not `retry`, so the rule `digest` does not clear the stop on a new image.
- devops-cli declares both steps in `.devops/roadmap.toml`.
- `docs/ROADMAP_WORKFLOW.md` and `docs/roadmap/implement.md` state the rule and the new class.
- The change fits one pull request.

Not in this change: the live run of a dotfiles item to a pull request has its own item (#3511), the refusal of GitHub to accept a push of a workflow file from the App needs its own item, and `read_draft` (the readiness read for a pull request outside the job) keeps its rule of an archived change.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-job`: The job runs the docs step and the archive step only where the target declares them
- `roadmap-failure-taxonomy`: A stop on a read-only path has its own class and is not retried

## Impact

- Code: `src/devops_cli/roadmap/implement_steps.py` (new), `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/roadmap/implement_pull.py`, `src/devops_cli/roadmap/failure.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`
- Files: `.devops/roadmap.toml` (new)
- Documents: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/implement.md`
- Tests: `tests/roadmap/test_roadmap_implement_project_steps.py`, `tests/roadmap/test_roadmap_failure.py`, `tests/support/roadmap_implement.py`

## Feasibility

- Code at `origin/main` (`1905269c`): `_finish_change` calls `_generate_docs` and then runs `openspec archive` with no condition, and `_scoped_rounds` calls `_generate_docs` after each fix. The premise holds.
- `.github/roadmap.toml`, which the refinement of the issue calls an existing file, does not exist in the repository (`find . -name roadmap.toml` finds nothing). So the change adds `.devops/roadmap.toml`. The directory `.devops/` holds the other per-repository files of devops-cli (`review.toml`, `survey.toml`).
- `trusted_config` in `implement_hooks.py` reads a file from `origin/<default>` with `git ls-tree` and `git show`, and gives None when the file is absent. `declared_steps` reads its file the same way. The test `test_the_declared_steps_are_read_from_the_commit_and_not_from_the_files` holds the commit over the checkout.
- `draft_readiness` for the kind `IMPLEMENT` refuses a change that is not archived. So a target that skips the archive step would stop at the step `ready` unless the decision knows the step is off. `ChangeFacts.archive_required` carries that.
- `stop_clear.py` clears by digest only a class whose action is `retry` in `ACTION_BY_CLASS` (#3481). A new class with the action `wait` is not cleared, with no edit to the rule. The refinement names an action `stop`; the type `FailureAction` has no such action, and `wait` is the action for a stop that only a person can change.
- Run on the base: the tests of this change fail there (`devops ci fail-to-pass --base origin/main`).

## Existing Tool Considered

Project code covers the need: `trusted_config` and `git` read a file from a ref, `tomllib` of the standard library reads TOML, and pydantic (already a dependency) validates the file. No external tool covers a gate on a repository-specific step, and no new dependency is added. No tool is built, so no build cost applies.
