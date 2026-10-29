# Proposal

## Why

Issue #1989: the evaluation set of intake's duplicate judgement (#1755) holds cases that a person judged, but nothing runs it against the live intake model. The tests replay recorded replies offline, so a prompt or model change that folds a related item again shows only as a wrong fold in a later intake run. Since #2223 (owner decision 2026-10-25), intake only names a possible duplicate, and a false duplicate is a P0 defect.

## What Changes

- A new command, `devops roadmap intake-eval`, runs each case of the set against the configured `analysis` model, one case at a time.
  - For each case it seeds an in-memory roadmap with the case's item, as an item with a Priority, and plans intake for the candidate with no write.
  - The verdict is `duplicate` when the decision names the item as the possible original, `new item` when it does not, and `skipped` when intake skips the candidate.
  - pydantic-evals scores each verdict against the person's verdict (`Dataset`, `EqualsExpected`, `ConfusionMatrixEvaluator`).
  - The command prints a table of the cases, the count that passed, the precision and the recall of the `duplicate` verdict, the false duplicates, and the model calls it made. It exits 0 when every case ran, and 1 when a case could not run.
  - `--dry-run` makes no request. It lists the cases and the one `analysis` call that each case makes.
- The run makes no embedding call. The roadmap of a case holds one item, so that item is the whole shortlist whatever the vectors are.
- The run reads the type labels from `.github/labels.yml` of the checkout, as intake reads them from the repository, and sends no GitHub request.
- The set moves from `tests/fixtures/roadmap/intake-duplicate-judgements.json` to `src/devops_cli/roadmap/intake_duplicate_cases.json`, so that an installed command can read it. The tests read the same file.
- A case's recorded reply (`answer`) becomes optional. The replay tests of #1755 take the cases that hold one.
- The set gains the eight wrong folds that the owner recorded on #1989 on 2026-10-24: #2178 to #2183, which intake judged duplicates of #2174, and #2146 and #2149, which it judged duplicates of #2143. The set holds 16 cases: 13 that are not duplicates and 3 that are.
- A new command is behavior that a person sees, so the change carries a spec delta: ADDED requirements in `roadmap-intake-duplicates`.
- This change fits one pull request.

## Capabilities

### Modified Capabilities

- `roadmap-intake-duplicates`: a command scores intake's duplicate judgement against the evaluation set.

## Impact

- New: `src/devops_cli/roadmap/duplicate_eval.py`, `tests/test_roadmap_duplicate_eval.py`.
- Moved: the evaluation set, to `src/devops_cli/roadmap/intake_duplicate_cases.json`.
- Changed: `src/devops_cli/commands/roadmap.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`, `tests/test_roadmap_intake.py`.
- Regenerated: `README.md`, `docs/CLI_REFERENCE.md`, `docs/commands/roadmap.md`, `docs/MCP_TOOLS.md` when the command is an MCP tool.

## Feasibility

- pydantic-evals 2.54.0, the locked version that ships with pydantic-ai, has `Dataset`, `Case`, `EqualsExpected`, `ConfusionMatrixEvaluator` and `set_eval_attribute`. A local probe on 2026-10-29 showed that `Dataset.evaluate_sync(task, max_concurrency=1)` runs the cases one at a time, keeps a task's attribute on its case, gives a case whose task raises as a `ReportCaseFailure` with its error, and leaves that case out of the confusion matrix. The matrix rows are the expected labels and the columns the predicted labels.
- `intake_candidate` with no `confirm` plans one new candidate and writes nothing (`src/devops_cli/roadmap/intake.py`). `InMemoryRoadmapStore` is product code with `seed_issue` and `seed_file` (`src/devops_cli/roadmap/memory_store.py`).
- `_Planner._shortlist` takes the nearest entries with no similarity floor, so a roadmap of one item gives a shortlist of that item for any vector.
- The live run is recorded in the pull request comment.

## Existing Tool Considered

pydantic-evals covers the need: it runs a dataset of cases through a task, scores each with a built-in evaluator, and builds a confusion matrix. It ships with pydantic-ai, which the project uses, and the gateway capability probes already score with it (#595). promptfoo needs Node.js and DeepEval adds a dependency; neither scores the verdict of intake's own code. The change builds the task that runs one case through intake (about 150 lines) and the report table, and no scorer. It deletes no code: the evaluation set moves.
