# Tasks

## 1. The owner label family and the rule of a claim

- [x] 1.1 Write failing tests in `tests/roadmap/test_roadmap_claim.py` and `tests/roadmap/test_roadmap_store_contract.py` for the scenarios of "One label family holds the owner of an Item" and of "A claim sets the owner label of one owner" and "A release clears the owner label": the owner read from the label, a person's label wins, a changed owner raises, a free claim, a person's claim over the Service, every refused claim, the same owner twice, a candidate, release of a held and a free Item, and the labels file declaring the label of every value of every field
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_claim.py tests/roadmap/test_roadmap_store_contract.py`
- [x] 1.2 Add `ItemField.OWNER`, the owner constants, `Item.owner` and the three labels to `.github/labels.yml`; write `src/devops_cli/roadmap/claim.py` and `RoadmapClaimError`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_claim.py tests/roadmap/test_roadmap_store_contract.py tests/roadmap/test_roadmap_intake.py`

## 2. The commands

- [x] 2.1 Write failing tests in `tests/roadmap/test_roadmap_claim.py` for the scenarios of "The claim commands write only with confirm": the plan without `--confirm`, the write with it, the dry run with no write, a refusal exits 1
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_claim.py`
- [x] 2.2 Add `devops roadmap claim` and `devops roadmap release` to `src/devops_cli/commands/roadmap.py`, with the help text, the messages and the dry run requests
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_claim.py tests/roadmap/test_roadmap_dry_runs.py`

## 3. The jobs leave out a claimed item

- [ ] 3.1 Write failing tests in `tests/roadmap/test_roadmap_stage_selection.py` and `tests/roadmap/test_roadmap_implement_selection.py` for the scenarios of "The job leaves out an item that an agent or a person claimed": a claimed item, a named item, the Service's own item
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_selection.py tests/roadmap/test_roadmap_implement_selection.py`
- [ ] 3.2 Add the check to the judge of `src/devops_cli/roadmap/stage.py` and of `src/devops_cli/roadmap/implement.py`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_selection.py tests/roadmap/test_roadmap_implement_selection.py`

## 4. The Service claims and a person's claim ends the Job

- [ ] 4.1 Write failing tests in `tests/roadmap/test_roadmap_implement_submit.py` and `tests/roadmap/test_roadmap_implement_job.py` for the scenarios of "The Service claims an Item for the Job it creates" and "A claim of a person or an agent ends the Job at the next group boundary": the claim at creation, the release at the report, a failed creation, a race with a person's claim, a person's claim kept at the report, the end at the boundary after group 1, before group 1 and after the last group, a run held by the Service, and a report that does not stop a claimed item
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_submit.py tests/roadmap/test_roadmap_implement_job.py`
- [ ] 4.2 Claim and release in `src/devops_cli/roadmap/implement_submit.py`; read the owner at the group boundary in `src/devops_cli/roadmap/implement_run.py` and end the item without a push or a pull request
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_submit.py tests/roadmap/test_roadmap_implement_job.py`

## 5. The worktree claims the issue

- [ ] 5.1 Write failing tests in `tests/core/test_repos_worktrees_add.py` for the scenarios of "A new worktree claims the issue for an agent": a free item, an item a person holds, a failed write, a refused issue, a dry run
  - Verification: `uv run devops ci test tests/core/test_repos_worktrees_add.py`
- [ ] 5.2 Claim after the worktree in `src/devops_cli/commands/repos.py`, and add `claimed` and `claim_error` to `WorktreeAddReport` in `src/devops_cli/git/worktree_add.py`
  - Verification: `uv run devops ci test tests/core/test_repos_worktrees_add.py tests/git/test_git_worktree.py`

## 6. The documents

- [ ] 6.1 Name the owner family in `docs/adr/0016-labels-hold-the-roadmap-items-fields.md`, regenerate the documents, and archive the change
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops openspec check`

## Workflow follow-up

- W7 (`devops roadmap inbox`) and W10 (stuck-item metrics) show a claim with no branch activity. No job removes a claim.
- Pending a person: run `devops gh labels sync` to create the three labels.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
