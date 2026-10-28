# Tasks

## 1. The store reads and writes labels

- [x] Write the failing contract tests: a field read from its label family, a person's second label, a field write that replaces the family in one request, the refusal of a person's change, the record block kept by a body write, a broken block read as empty, Items and Candidates by the priority label
  - Verification: `uv run devops ci test tests/test_roadmap_store_contract.py tests/test_roadmap_github_store.py`
- [x] Rewrite `store.py`, `memory_store.py` and `github_store.py` on labels and the record block; delete `BoardEntry`, `BoardField`, `FieldOption`, `AddedItem`, `add_item`, the card reads and edits, the board listing cache, `graphql_spend` and their tests
  - Verification: `uv run devops ci test tests/test_roadmap_store_contract.py tests/test_roadmap_github_store.py`
- [x] Move the Projects reads that `devops gh project` uses from `roadmap/board_read.py` to `github/project_read.py`, delete the rest, and move their tests and fakes
  - Verification: `uv run devops ci test tests/test_github_project_read.py tests/test_github_projects.py tests/test_github_projects_reconcile.py`

## 2. The roadmap jobs

- [x] Write the failing tests: intake places a candidate with labels and sends no Projects request, a stopped placement is a candidate again, return sets `status/new`, the Service round opens no roadmap file, the items gauge counts the Items
  - Verification: `uv run devops ci test tests/test_roadmap_intake.py tests/test_roadmap_return.py tests/test_roadmap_run.py tests/test_github_metrics.py`
- [x] Change intake, return, run, the request plans and `devops roadmap` to the label store; delete `roadmap/config.py`, `.github/roadmap.toml`, the board filters, `log_round_spend`, `service_pause_until` and the `--ref` of refine, run and return
  - Verification: `uv run devops ci test tests/test_roadmap_intake.py tests/test_roadmap_return.py tests/test_roadmap_run.py tests/test_roadmap_dry_runs.py tests/test_roadmap_refine.py`
- [x] Open the store with no configuration in the metrics, `devops gh issues triage` and the survey
  - Verification: `uv run devops ci test tests/test_github_metrics.py tests/test_gh_cmd.py tests/test_github_issues.py tests/test_survey_capabilities.py`

## 3. The other users of the board

- [x] Write the failing test, then make `devops pr check-readiness` block a pull request whose one issue holds no `priority/*` label, read in the closing-issues query
  - Verification: `uv run devops ci test tests/test_pr_cmd.py`
- [x] Drop the "awaiting intake" line of `devops gh project reconcile` and the `Job record` field of the project template
  - Verification: `uv run devops ci test tests/test_github_projects_reconcile.py tests/test_gh_project_workflows.py`
- [x] Declare the four label families in `.github/labels.yml`
  - Verification: `uv run devops ci test tests/test_roadmap_intake.py`

## 4. Documentation

- [x] Write ADR 0016 and the notes on ADR 0001, 0002 and 0003; change `CONTEXT.md`, `README.md`, `docs/SDLC.md`, `docs/ROUTINE_TASKS.md` and the knowledge base; regenerate the command references with `devops docs generate --sync-readme`
  - Verification: `uv run devops ci test tests/test_docs.py`

## 5. Verification

- [x] Verify the fail-to-pass check run against `origin/main`
  - Verification: `uv run devops ci fail-to-pass --base origin/main`
- [x] Verify that the full gate passes
  - Verification: `uv run devops ci`

## Workflow follow-up

- Pending a person: apply the label migration that `.data/agent/scratch/board_to_labels.py` prints, for each managed repository, and delete the old labels it lists.
- Pending a person: delete `.github/roadmap.toml` from the other managed repositories, and the `Job record` field from board 12.
- Pending a person: review the diff in tuicr (`tuicr -r origin/main..HEAD`).
