# Tasks

## 1. Record the Status that a claim replaces

Kind: behavior. Reads: `src/devops_cli/roadmap/status_sync.py`, `tests/roadmap/test_roadmap_claim.py`. Changes: `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/pull_status.py`, `tests/roadmap/test_roadmap_claim.py`.

- [ ] 1.1 Add `test_an_agent_claim_records_the_replaced_status` to `tests/roadmap/test_roadmap_claim.py`: an agent claim of a Planned Item leaves `Planned` under `claim.replaced_status` and the Item holds `status/in-progress`, and a claim of an Item with no Status label leaves no `claim.replaced_status`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_claim.py` fails on the base
- [ ] 1.2 Add `ClaimRecordKey` with `REPLACED_STATUS = "claim.replaced_status"` to `src/devops_cli/roadmap/stores/store.py`, and join it to `JobRecord`, to `_JOB_RECORD_KEYS` and to `__all__`. In `src/devops_cli/roadmap/pull_status.py` pass `{ClaimRecordKey.REPLACED_STATUS: item.status}` as the marks of the `write_status` call of `set_claimed_status`, so the Status that the claim replaces lands in the same write as In Progress
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_claim.py` passes

## 2. Restore the Status when a release clears an agent claim

Kind: behavior. Reads: `src/devops_cli/roadmap/pull_status.py`, `src/devops_cli/roadmap/implement/implement_outside.py`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/git/branch_form.py`. Changes: `src/devops_cli/roadmap/claim.py`, `src/devops_cli/roadmap/status_sync.py`, `tests/roadmap/test_roadmap_claim.py`.

- [ ] 2.1 Add `test_a_release_restores_the_status_of_an_agent_claim` to `tests/roadmap/test_roadmap_claim.py`: claim an Item that holds `status/planned`, set In Progress, release the claim, and the Item holds no owner label, `status/planned`, and `require_startable` returns without raising; add the cases of a Ready Item, an open pull request, a running Job, a Blocked Item, a Status that a person set, and a closed issue that keeps `status/planned` and records no Status write
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_claim.py` fails on the base
- [ ] 2.2 Add `released_facts` to `src/devops_cli/roadmap/claim.py`: it gives None when the Item is closed, when its Status label is not In Progress, or when its job record does not hold In Progress; else it gives `StatusFacts` with `plan_merged` when `claim.replaced_status` holds `Planned`, `job_active` from `job_holds`, and `pull_open` when an open pull request of `store.open_pulls()` has a head branch that `issue_of_branch` maps to the Item. In `apply_claim`, after clearing an `owner/agent` claim, write the Status through `write_status` on the Item read again. Add the release of an agent claim to the list of writers in the docstring of `src/devops_cli/roadmap/status_sync.py`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_claim.py` passes

## 3. Name the release Status change in the workflow page

Kind: other. Reads: `src/devops_cli/roadmap/stores/store.py`, `docs/ROADMAP_WORKFLOW.md`. Changes: `docs/ROADMAP_WORKFLOW.md`, `tests/invariants/test_roadmap_workflow_doc.py`.

- [ ] 3.1 Rewrite the claim table row of `docs/ROADMAP_WORKFLOW.md` for `owner/agent` or `owner/human` and `devops roadmap release`: a release of `owner/agent` clears the owner and writes the Status that the Item's facts give, and a release of `owner/human` clears the owner and changes no Status. Add one sentence below the table that names the facts: Planned when the plan is merged, In Progress while a Job or an open pull request holds the Item, Ready otherwise, and no Status write for a Blocked Item, a closed issue or a Status that a person set. Add `claim.replaced_status` in a code span to the record-key table, and import `ClaimRecordKey` and add it to the `RECORD_KEYS` tuple of `tests/invariants/test_roadmap_workflow_doc.py`
  - Verification: `$ uv run devops ci test tests/invariants/test_roadmap_workflow_doc.py` passes
- [ ] 3.2 Edit `docs/ROADMAP_WORKFLOW.md` in its claim table row, in the sentence below it and in its record-key table, and `tests/invariants/test_roadmap_workflow_doc.py` in its `RECORD_KEYS` tuple
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
