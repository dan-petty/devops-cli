# Tasks

## 1. The rules, the discard and the guards of the step

Kind: behavior. Reads: `src/devops_cli/roadmap/claim.py`, `src/devops_cli/roadmap/watch_row.py`. Changes: `src/devops_cli/roadmap/steps/review.py`, `src/devops_cli/roadmap/steps/review_facts.py`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/commands/roadmap_step_review.py`, `tests/roadmap/steps/test_roadmap_step_review.py`.

- [x] 1.1 Write failing tests: a new fact on a judged head gives a new verdict with no second model call; a discard deletes the branch first, then closes, then returns the item; a failed delete closes nothing; a call on the closed pull request ends a discard; a discard with no withdraw writes nothing; a shared branch is left for a person; a discard of the model alone only labels and comments; a person's ready mark stays; a live `stage.job` skips; `owner/service` does not stop
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_step_review.py`
- [x] 1.2 Run the rules on each call, record the source of the verdict, order and repair the discard, check the shared branch and the withdraw before the first write, read the actor of the ready mark, and use `claim_labels` and `stage.job`
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_step_review.py`

## 2. The ready hold of the watch row

Kind: behavior. Changes: `src/devops_cli/roadmap/steps/watch.py`, `src/devops_cli/roadmap/watch_row.py`, `tests/roadmap/steps/test_roadmap_due_steps.py`, `tests/roadmap/test_roadmap_watch_row.py`.

- [x] 2.1 Write failing tests: READY is not due for a verdict label other than `verdict/mergeable`; the watch row leaves a green plan draft with `verdict/issue-changed` a draft
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_due_steps.py tests/roadmap/test_roadmap_watch_row.py`
- [x] 2.2 Add `ready_held` and the labels of `WatchState`, and pass the labels from both read paths of the watch row
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_due_steps.py tests/roadmap/test_roadmap_watch_row.py`

## 3. The wait on CI infrastructure and the answered issue text

Kind: behavior. Changes: `src/devops_cli/roadmap/steps/review.py`, `src/devops_cli/roadmap/steps/review_facts.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/config/defaults.py`, `tests/roadmap/steps/test_roadmap_step_review.py`, `tests/roadmap/test_roadmap_limit_classes.py`, `tests/security/test_config_declarations.py`.

- [x] 3.1 Write failing tests: a wait on CI infrastructure logs a line and ends after `roadmap.review.infra_wait_hours` with one comment; an issue text that an Issue changed verdict answered gives the next head its own verdict
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_step_review.py`
- [x] 3.2 Add the setting, the wait limit and `review.text`
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_step_review.py tests/roadmap/test_roadmap_limit_classes.py tests/security/test_config_declarations.py`

## 4. Documents

Kind: documents. Changes: the generated reference documents.

- [x] 4.1 Regenerate the reference documents with `devops docs generate`
  - Verification: `$ uv run devops ci docs`

## Criteria

- Group 1: The rules run on each call, a discard can never leave a closed pull request with an item that does not go back, a model discard acts only through a person, and the guards match the watch row.
- Group 2: No ready mark of the watch row undoes a verdict that sent the work back.
- Group 3: A wait on CI infrastructure has a limit and a log line, and one issue text gives one Issue changed verdict.
- Group 4: The documents name the new setting.

## Workflow follow-up

- #6011: the trigger and the launcher of the step, and the decision of the owner whether the cap gives a deterministic discard.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
