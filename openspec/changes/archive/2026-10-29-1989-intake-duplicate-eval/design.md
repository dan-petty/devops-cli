# Design

## Context

`devops roadmap intake` compares a candidate with the items of the roadmap. It embeds the texts, takes the nearest items as a shortlist, and asks the `analysis` model for a proposal. Code then reads the reply (`_judge`): an item named as the original with a shared change is a possible duplicate, and one named with no shared change is a related item. The evaluation set records, for each candidate, the item it was compared with and a person's verdict.

## Decisions

### 1. Score with pydantic-evals

Each case is a `Case` whose expected output is the person's verdict (`duplicate` or `new item`). `EqualsExpected` scores each case, and `ConfusionMatrixEvaluator` counts the verdicts. The precision and the recall of the `duplicate` verdict come from that matrix: a false duplicate is a case a person judged `new item` that intake judged `duplicate`.

- Rejected: `PrecisionRecallEvaluator`. Evidence: it builds a curve from a numeric score and thresholds (`pydantic_evals/evaluators/report_common.py`), and intake gives a verdict with no score.
- Rejected: a scorer written here. Evidence: AGENTS.md rule 3, and the locked pydantic-evals already has both evaluators.

### 2. One item per case, through intake's own code

Each case seeds a new `InMemoryRoadmapStore` with `.github/labels.yml` and the case's item, as an open issue with a Priority, and plans intake for the candidate with `intake_candidate` and no `confirm`. The verdict is read from the decision, so `_judge` turns the reply into a verdict as it does in a real run.

- Rejected: the live roadmap on GitHub. Evidence: several items of the set are closed or changed since, the run would send GitHub requests, and the other open items would change the shortlist from run to run.
- Rejected: a direct call of the model's `propose` with a request built here. Evidence: it skips `_judge`, so a reply that names an original with no shared change would count as a duplicate, which intake does not do.

### 3. No embedding call

The run gives every text the same vector. With one item in the roadmap, `_Planner._shortlist` takes that item whatever the vectors are, because it has no similarity floor.

- Rejected: the configured embedder. Evidence: it sends one request for each case and changes no shortlist.

### 4. The set is package data

The set moves to `src/devops_cli/roadmap/intake_duplicate_cases.json`, read with `importlib.resources`.

- Rejected: keep it under `tests/fixtures`. Evidence: an installed command has no `tests` directory, and product code that reads a test fixture couples the two.

### 5. Labels from the checkout

The run reads `.github/labels.yml` from the root of the checkout it runs in (`find_repo_root`). With no such file it stops before any model call, and the error names the file.

- Rejected: read the labels through GitHub. Evidence: one more request and a GitHub identity for a run that is otherwise only model calls.

### 6. One case at a time, and the exit status

`evaluate_sync` runs with `max_concurrency=1`, as AGENTS.md rule 13 asks for model calls. The command exits 0 when every case ran, whatever the score, because the score is the report. It exits 1 when a case could not run, for example when the gateway does not answer, and the table names the error.

## Risks / Trade-offs

- The score is for one run of a model that does not always give the same reply. → The table gives the model's reason for each case, so a person reads why a case failed.
- A case's item has no neighbours, so the run does not measure the shortlist. → The set measures the judgement, which is where the wrong folds came from.
