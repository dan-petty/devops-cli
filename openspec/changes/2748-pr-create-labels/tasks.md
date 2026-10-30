# Tasks

## 1. One rule for the labels of a title

- [ ] 1.1 In `tests/test_pr_title_labels.py`, assert that `title_labels` gives `type/bug` and `scope/ai` for `fix(ai): x`, only the type for `docs: x`, nothing for `A plain title`, and the undeclared label for `fix(zzz-unknown): x`, and verify that `uv run devops ci test tests/test_pr_title_labels.py` fails on the base
- [ ] 1.2 Add `src/devops_cli/roadmap/title_labels.py` with `title_labels` and `declared_label_names`, make `_title_labels` and `_Run.declared` of `roadmap/intake.py` call them, and verify that `uv run devops ci test tests/test_pr_title_labels.py tests/test_roadmap_intake.py` passes
- [ ] 1.3 Run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 2. devops pr create adds the labels

- [ ] 2.1 In `tests/test_pr_title_labels.py`, assert the scenarios of `specs/pr-title-labels/spec.md` against the in-memory roadmap store: the labels of a fix with a scope, the warning for an undeclared scope, the exit 1 that names pull request, labels and reason for a refused label and a missing label file, the Status that is still set, no label in a dry run, and the REST fallback path, and verify that `uv run devops ci test tests/test_pr_title_labels.py` fails on the base
- [ ] 2.2 Add `src/devops_cli/roadmap/pull_labels.py`, let the in-memory store accept a pull request number in `label_issue`, and call the labels from `devops pr create` on both paths with the messages in `lang/en/messages.py`, and verify that `uv run devops ci test tests/test_pr_title_labels.py tests/test_pr_cmd.py tests/test_pr_status.py` passes
- [ ] 2.3 Name the labels in the help of `devops pr create`, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- The stage job and the implement job should give their pull requests the labels of the title with `title_labels`. A follow-up item covers both (see `design.md`).
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
