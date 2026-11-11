# Design

## Decisions

- **A Python table, not a data file.** `WORKFLOW_LABELS` is a tuple of `LabelSpec` in `roadmap/workflow_labels.py`. It is typed, it needs no package data, and a test binds it to the constants that read or write the labels.
- **The file reader merges.** `declared_label_specs` gives the workflow labels first, then the labels of the file. So every reader of `.github/labels.yml` (intake, the inbox, `devops pr create`, the stage and implement jobs, onboard) gets the workflow labels with no change at its call site. A workflow label in an old file keeps the package color and description, so an old copy cannot change them.
- **Row 4 works with no file.** When row 3 is missing or not readable, row 4 compares the workflow labels only. A repository with no file still learns which workflow labels it lacks.
- **One color for each meaning.** `priority/p0` to `priority/p3` take `status.error`, `status.warn`, `accent` and `fg-muted`. A `type/*` label that adds behavior takes `data.cat.1`, one that fixes a defect (`type/bug`, `type/security`, the critical-fix set) takes `data.cat.2`, and one that keeps behavior (`type/refactor`, `type/infra`, `type/test`) takes `data.cat.3`. A label that stops work until someone acts (`status/blocked`, `plan/needs-fix`, `needs-split`, `hold-release`) takes `border-strong`. Each other label takes `border`.
- **`needs-split` is a workflow label.** The stage job reads it (`stage.py`), so the package declares it. The test cannot import the private constant of the stage job, so it collects the public constants only.

## Rejected alternatives

- **A YAML file in the package.** The same format as `.github/labels.yml`, but it needs package data and gives no names to the colors.
- **Probot Settings or `github-label-sync`.** Each syncs labels from a file in each repository, so the copies drift again.
- **Keep the workflow labels in each `.github/labels.yml`.** That is the cause of the drift: the 6 other repositories hold an old copy.
