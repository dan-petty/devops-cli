# Proposal: #4652

## Why

Each repository that the roadmap jobs serve holds its own hand copy of the workflow labels in `.github/labels.yml`, and the copies drift. devops-cli's file holds 83 labels: 45 `scope/*` labels, the release labels, and the labels that the roadmap code reads or writes. The other repositories hold an older copy, so a label that the Service writes can be absent on GitHub. `devops roadmap onboard` checks only that the file is valid and holds a `type/*` label, so it cannot find a missing workflow label. Closes #4652.

## What Changes

- A new module `src/devops_cli/roadmap/workflow_labels.py` declares the 31 workflow labels once, with the color and the description of each: 9 `type/*`, 6 `status/*`, 4 `priority/*`, 3 `value/*`, 3 `effort/*`, 3 `owner/*`, `plan/needs-fix`, `source/agent` and `needs-split`.
- Each label color is a light token color of the design spec (#4738, folded in from the tracker #4735): one color for each priority, three data colors for the `type/*` labels, and two grays for the other labels. `LabelColor` names the token of each color. No label uses a brand color.
- `declared_label_specs` (`roadmap/title_labels.py`) gives the workflow labels, then each label of the `.github/labels.yml` text that no workflow label names. Intake, the inbox, `devops pr create`, the implement job and the stage job read the labels through it, so they get the workflow labels in every repository. `declared_type_labels` goes: intake and `devops roadmap eval intake` read `WORKFLOW_TYPE_LABELS`.
- `devops roadmap onboard` row 3 checks that `.github/labels.yml` is present and valid. Row 4 compares GitHub with the workflow labels and the labels of the file, and the output lists each missing label. `--confirm` creates the missing labels with `POST`, as before.
- `devops gh labels sync` applies the workflow labels and the labels of `--file`.
- devops-cli's `.github/labels.yml` holds only its own labels: the 45 `scope/*` labels and the 4 release labels, each with a gray token color. The three `review/*` labels go, because no code reads or writes them.
- Intake drops its error for a labels file with no `type/*` label, because the package always gives the type labels.

## Capabilities

- `roadmap-onboard` (modified): rows 3 and 4, and the type rule.
- `roadmap-item-labels` (modified): the package declares the workflow labels.
- `roadmap-intake-title-labels` (modified): the model picks a type of the workflow labels.
- `roadmap-intake-duplicates` (modified): the evaluation run reads the workflow labels and the labels file of the checkout.

## Impact

- Each repository gets the same workflow labels from one list. `devops roadmap onboard --confirm` or `devops gh labels sync` creates the missing ones.
- The other repositories keep their old `.github/labels.yml` until their kit pull request (#4653) replaces it. A workflow label in an old file keeps the color and the description of the package.
- The labels on GitHub keep their old colors until a person runs `devops gh labels sync`, which updates the colors and the descriptions. Onboard lists them as differing and never edits them.
- The `review/*` labels stay on GitHub, because a sync never deletes a label.

## Feasibility

- `git grep` over `src/` shows the labels that the code reads or writes: the field families (`FIELD_VALUES` and `field_label` in `roadmap/stores/store.py`), `CONST_ROADMAP_COMMIT_TYPE_LABELS`, `CONST_ROADMAP_EPIC_LABEL`, `CONST_ROADMAP_CRITICAL_FIX_LABELS`, `CONST_ROADMAP_SOURCE_AGENT_LABEL`, `PLAN_NEEDS_FIX_LABEL` (`stage_verify.py:84`) and `needs-split` (`stage.py:299`). That is 31 labels.
- `git grep "review/approved\|review/ai-reviewed\|review/changes-requested" -- src .github/workflows` finds nothing. The last reader went with the bespoke release path in #1952. So the `review/*` labels are no workflow labels, and the issue's count of 33 changes to 31.
- `devops gh api repos/dan-petty/homelab/labels` lists no `status/planned`, no `owner/*` and no `plan/needs-fix`, and its `.github/labels.yml` is blob `8886b989`, the old hand copy.
- `onboard.py:123-176` reads only the validity of the file and a `type/*` label.
- The token JSON of #4738 is not on `main` yet. The draft of that issue holds each hex value of `LabelColor`: `color-status-error`, `color-status-warn`, `color-accent`, `color-fg-muted`, `color-border-strong` and `color-border` in the light tokens, `color-data-cat-1` to `color-data-cat-3` in the base tokens. So the test of this change holds each label color to `LabelColor`, and a later test can hold `LabelColor` to the token file when #4738 merges.

## Existing Tool Considered

The GitHub REST labels API creates the labels, as today. The Probot Settings app and `github-label-sync` sync labels only from a file in each repository, so the copies drift again. To build: about 80 lines of code, 31 lines of table data and 4 tests, about 250,000 tokens and 3 hours.
