## 1. The contract of the title check

- [x] 1.1 Write the failing test `test_the_title_check_allows_exactly_the_declared_scopes` in `tests/invariants/test_workflow_contracts.py`. Verify: `uv run devops ci test tests/invariants/test_workflow_contracts.py`
- [x] 1.2 Declare the 15 scopes in `.github/labels.yml`. Verify: `uv run devops ci test tests/invariants/test_workflow_contracts.py tests/commands/test_pr_title_labels.py`
- [x] 1.3 Set `scopes` in `.github/workflows/pr-title.yml`. Verify: `uv run devops ci test tests/invariants/test_workflow_contracts.py`
- [x] 1.4 Say in `CONTRIBUTING.md` that the scope of a title is a declared scope, and run `uv run devops docs generate --sync-readme`.

## 2. The delivery title

- [x] 2.1 Write the failing tests `test_the_delivery_title_drops_a_scope_that_no_label_declares` and `test_the_title_of_the_pull_request_has_no_scope_that_the_labels_file_lacks`. Verify: `uv run devops ci test tests/roadmap/test_roadmap_stage_title.py tests/roadmap/test_roadmap_implement_job.py`
- [x] 2.2 Make `delivery_title` leave out a scope that `.github/labels.yml` does not declare, read the file in the implement job, and record it in the delta of `roadmap-implement-job`. Verify: `uv run devops ci test tests/roadmap/test_roadmap_stage_title.py tests/roadmap/test_roadmap_implement_job.py`
- [x] 2.3 Declare the scopes `scan`, `contributing`, `sdlc`, `fail-to-pass`, `argocd`, `output` and `gate`, and correct the title examples in `CONTRIBUTING.md` and the knowledge base. Verify: `uv run devops ci test tests/invariants/test_workflow_contracts.py`

## 3. Verification

- [ ] 3.1 Run `uv run devops ci fail-to-pass --base origin/main`.
- [ ] 3.2 Run the full `uv run devops ci` once.
- [ ] 3.3 Archive the change with `uv run devops openspec archive 2800-scope-labels-for-git-and-agents`.
