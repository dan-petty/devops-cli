# Proposal: The open step checks each pull request attribute, and a row opens a pushed branch

## Why

Closes #5974. The stage job and the implement job write the title, the body and the labels of a pull request at the end of a long model run, and nothing checks these attributes against the rules of CI before the pull request exists. On 2026-11-16 the bot pull requests #5940 and #5920 had the type `test`, which `release-please-config.json` hides, while they change runtime code. The check `Semantic PR title` failed, and a person changed each title (`fix` for #5940, `feat` for #5920). The owner decided on 2026-11-16 that the creation of a pull request becomes a separate job that owns its attributes (#5014).

## What Changes

- The open step (`src/devops_cli/roadmap/steps/open.py`) checks each attribute before it creates or updates a pull request:
  - **Type.** When the type is hidden and the diff changes runtime code, the step writes `feat` for a diff that adds a runtime file, else `fix`. It calls `hidden_type_problem` of `src/devops_cli/github/release_title.py`, which the `Semantic PR title` workflow runs. The step reads the diff only for a hidden type.
  - **Scope.** The step removes a scope that `.github/labels.yml` does not declare, as `delivery_title` does (#2800).
  - **Summary and form.** `title_problems` of `pull_form.py`, which a test holds equal to the summary pattern and the scopes of the workflow.
  - **Body.** A plan body has the whole form of `plan_body_problems`. A delivery body closes only the delivered issue, in one line `Closes #<issue>`, and has at most `BODY_MAX_CHARS` characters before its trailers.
  - **Labels and Status.** The labels come from the checked title, so the type label follows the type that the step wrote. The step keeps the Status write of #5020.
  - A problem that no rule can fix, such as a long summary, refuses the write and names every problem.
- A new row `open` of the status lane of the Service, after `stage` (`src/devops_cli/roadmap/open_row.py`). It finds the pushed branch that the job record of an open item names in `implement.branch` and that has no pull request, and runs the open step for it. The setting `roadmap.open.mode` is `off`, `plan` or `on`, and it starts in `plan`. The row is due every `roadmap.open.interval_minutes` (7 by default) and on a first run.
- Stage and implement keep their call of the open step. #5029 and #4719 remove it.

## Capabilities

- Modified: `roadmap-stage/open` (new requirements).

## Impact

- The open step sends one more read for each call (the release-please config), one read of the labels file for a call with no store, and one compare read for a hidden type.
- The Service gets one more lane and its clone. A round reads the heads of `origin` with git and sends a GitHub request only for a candidate branch.
- The change fits one pull request.

## Feasibility

- `src/devops_cli/roadmap/steps/open.py` on `origin/main` ef1a280bc writes `request.title` and `request.body` as given. It reads the labels file only to add the title labels.
- `devops gh api repos/dan-petty/devops-cli/issues/5940/timeline` shows the rename `test(roadmap): ...` to `fix(roadmap): ...`, and #5920 shows `test(k8s): ...` to `feat(k8s): ...`. The files of #5920 add `src/devops_cli/k8s/volume_move_measure.py`. The files of #5940 change `src/devops_cli/lang/en/help.py` and `messages.py` and add no runtime file.
- `.github/workflows/pr-title.yml` runs `python -m devops_cli.github.release_title`, and `tests/invariants/test_workflow_contracts.py` holds the action inputs equal to `SUMMARY_MAX_CHARS` and the labels file. So each CI rule is already in a project module, and this change moves no rule.
- The implement job records `implement.branch` in `_start`, before its first push. The stage job records `stage.branch` only after it opens the plan pull request, and removes its orphans itself (#4051).

## Existing Tool Considered

`amannn/action-semantic-pull-request` checks a title after the pull request exists, and it cannot run before the write. No open tool knows the hidden types of a release-please config or the issue of a roadmap item. The change reuses `release_title`, `pull_form`, `title_labels`, `delivery_title`, `build_body` and the compare read of the GitHub client. Cost to build: about 0.4M agent tokens and 3 agent-hours.
