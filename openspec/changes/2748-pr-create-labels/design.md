# Design

## The rule has one home

`title_labels(title, declared)` in `roadmap/title_labels.py` returns the type label, the scope label, and the scope label that the file does not declare. It uses `commit_type`, `commit_scope` and `CONST_ROADMAP_COMMIT_TYPE_LABELS`. Intake builds its reason lines from this result, and `devops pr create` builds its labels and its warning from it. The parse of `.github/labels.yml` moves to `declared_label_names` in the same module. Each caller keeps its own error text, because the text of intake speaks about candidates.

## When the labels are added

The labels are added after the pull request exists, through `RoadmapStore.label_issue`, in the same place as the Status (#2717). The command needs the number of the pull request, and both the `gh pr create` path and the REST fallback path give it. The command reads the label file on the base branch of the pull request (the default branch when `--base` is not given).

A failure does not undo the pull request. The pull request is the product of the command, and a person can add a label by hand. The command exits 1, names the pull request and the labels, and leaves the pull request open, as it does for a failed Status write. Both writes run: an error in the first must not hide the second. One exit 1 reports either failure.

## Rejected alternatives

- `gh pr create --label`. It needs the same title rule and the same declared check. It uses GraphQL, the path that `_fallback_create_pr` leaves when the quota is out, and the REST `POST /pulls` fallback has no label field. A refused label would stop the creation. The issues labels endpoint works for both paths.
- Read `.github/labels.yml` from the local checkout with `load_label_specs`. This fails for `--repo` on another repository, and a branch that edits the file would declare labels that GitHub does not hold yet. The file on the base branch is what intake reads.
- Read the labels of the repository from `repos/{repo}/labels`. This answers a different question: it lists the labels that exist, not the labels the project declares. Intake and the audit use the declared file, and the issue names it.
- Copy `_title_labels` into `pr.py`. It would give two copies of one rule, which drift. AGENTS.md rule 3 and the issue forbid it.
- Delete the pull request when a label fails. The pull request may already have a branch review, a Status, and links. The failure is small and fixable by hand.
- Add `--label` options to `devops pr create`. The issue says the title is the only source.

## The stage and implement jobs

The stage job opens its draft with `create_draft_pull` and deletes the remote branch when GitHub does not make the pull request. A label failure there must not delete the branch of an open pull request, and must not leave the marks of the job unset, so the failure path needs its own design. The implement job later sets a new title and body, so the labels must follow the new title, which is a second write. Neither is small and safe. A follow-up item covers both. They should call `title_labels` and `RoadmapStore.label_issue`, the pieces this change adds.
