# Proposal

## Why

The claim of an agent writes In Progress through the one Status writer (`src/devops_cli/roadmap/pull_status.py:def set_claimed_status`), but the release writes only the owner field (`src/devops_cli/roadmap/claim.py:def apply_claim`). The item then holds In Progress with no owner, no Job and no pull request, and #5118 shows that no job acts on it: the sweep and the start check take only Ready or Planned, and the claim line of the inbox needs an owner. Two texts give the release as the remedy, so the release must restore the Status.

## What Changes

- The claim of an agent records the Status that the Item held before the claim under the record key `claim.replaced_status`, in the same write that sets In Progress.
- `devops roadmap release` writes the Status that the facts of the Item give after it clears an `owner/agent` claim, through `write_status`.
- The release writes no Status for a closed issue, for a Status label that is not In Progress, or for an In Progress label that the job record does not hold.
- The claim table of `docs/ROADMAP_WORKFLOW.md` names the Status change of a release of `owner/agent`, and the record-key table names `claim.replaced_status`.
- The change carries a spec delta in `roadmap-item-claim`, because the Status of an Item after `devops roadmap release` is observable behavior of a command.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-item-claim`: A claim records the Status it replaces, A release of an agent claim restores the Status, A release keeps a Status that a job did not set

## Impact

- Code: `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/pull_status.py`, `src/devops_cli/roadmap/claim.py`, `src/devops_cli/roadmap/status_sync.py`
- Documents: `docs/ROADMAP_WORKFLOW.md`
- Tests: `tests/roadmap/test_roadmap_claim.py`, `tests/invariants/test_roadmap_workflow_doc.py`

## Feasibility

- The probes confirm that each path the plan cites is a file of the staging commit: "The path `src/devops_cli/roadmap/claim.py` is a file of the staging commit." and "The path `src/devops_cli/roadmap/status_sync.py` is a file of the staging commit." and "The path `docs/ROADMAP_WORKFLOW.md` is a file of the staging commit."
- The stuck item is confirmed by the staged code: `src/devops_cli/roadmap/status_sync.py:70:_WRITTEN_FROM = frozenset({CONST_ROADMAP_STATUS_READY, CONST_ROADMAP_STATUS_PLANNED})` keeps the sweep away, `src/devops_cli/roadmap/implement/implement_outside.py:36:_STARTABLE = frozenset({CONST_ROADMAP_STATUS_READY, CONST_ROADMAP_STATUS_PLANNED})` refuses the start, and `src/devops_cli/roadmap/inbox.py:314:def _claim_lines(` needs an owner.
- The claim writes In Progress: `src/devops_cli/roadmap/pull_status.py:def set_claimed_status` writes it through `write_status` with the agent-claimed fact, and `src/devops_cli/roadmap/claim.py:def progress_as_agent` calls it after `src/devops_cli/roadmap/claim.py:def claim_as_agent`.
- The release writes the owner only: `src/devops_cli/roadmap/claim.py:def apply_claim` writes one field, `ItemField.OWNER`, and returns before it when the Item holds the target owner.
- `read_file` of `src/devops_cli/roadmap/stores/store.py` lines 1005-1050 showed that a field write records the value in the job record: `src/devops_cli/roadmap/stores/store.py:1019:Set or clear the field's label family on the Item's issue, and record the value`. So the record holds In Progress after a claim, and a Status that a person set by hand differs from it.
- The staged values of the constants the plan relies on, read at `src/devops_cli/config/constants.py` lines 3750-3810: `src/devops_cli/config/constants.py:3756:CONST_ROADMAP_STATUS_READY: Final[str] = "Ready"`, `src/devops_cli/config/constants.py:3757:CONST_ROADMAP_STATUS_PLANNED: Final[str] = "Planned"`, `src/devops_cli/config/constants.py:3758:CONST_ROADMAP_STATUS_IN_PROGRESS: Final[str] = "In Progress"`, `src/devops_cli/config/constants.py:3760:CONST_ROADMAP_STATUS_BLOCKED: Final[str] = "Blocked"` and `src/devops_cli/config/constants.py:3804:CONST_ROADMAP_OWNER_AGENT: Final[str] = "Agent"`.
- The Status set is the six members that the read showed under `src/devops_cli/config/constants.py:3761:CONST_ROADMAP_STATUS_VALUES: Final[tuple[str, ...]] = (` at lines 3762-3768: New and In Review are never written by the release, In Progress is the label the release reads, Ready and Planned are the two Statuses the release writes, and Blocked stays.
- `search_code` with `ClaimRecordKey` found no match, so the key family is new, and `read_file` of `src/devops_cli/roadmap/stores/store.py` lines 360-400, 660-700 and 1170-1200 showed the shape that it copies and each place it joins: `src/devops_cli/roadmap/stores/store.py:371:class ConsolidateRecordKey(StrEnum):`, `src/devops_cli/roadmap/stores/store.py:379:JobRecord = dict[`, `src/devops_cli/roadmap/stores/store.py:677:_JOB_RECORD_KEYS = frozenset(` and `src/devops_cli/roadmap/stores/store.py:1188: "ConsolidateRecordKey",`.
- `read_file` of `tests/invariants/test_roadmap_workflow_doc.py` lines 30-160 showed that the page must name each record key: `tests/invariants/test_roadmap_workflow_doc.py:48:RECORD_KEYS = frozenset(` builds the set from the record families, and `tests/invariants/test_roadmap_workflow_doc.py:151:problems += [f"record key {key} is missing" for key in sorted(RECORD_KEYS - named_keys)]` refuses a page that leaves one out, so the doc group joins `ClaimRecordKey` to that tuple and names the key in a code span.
- `read_file` of `docs/ROADMAP_WORKFLOW.md` lines 60-135 showed the claim table row `docs/ROADMAP_WORKFLOW.md:82:A person or an agent runs`, whose To state is `No owner` and which names no Status, and the record-key table at `docs/ROADMAP_WORKFLOW.md:100:| State | Label | Set by | Record keys that hold the facts |`.
- The finding `spec_delta_wrong` is corrected: `docs/ROADMAP_WORKFLOW.md:69:A person merges the pull request (G2) and the issue closes` gives the workflow `clear-status.yml` as the actor that clears the labels of a closed issue, so the closed-issue scenario now asserts that a release writes no Status and keeps the label, and `src/devops_cli/roadmap/claim.py:103:A release of a closed issue is allowed: it clears a label that nothing else would clear.` confirms that the release clears the owner alone.
- `src/devops_cli/roadmap/claim.py:def apply_claim` needs a client of GitHub: the store reads the Item and writes the owner label and the Status label.
- `src/devops_cli/roadmap/status_sync.py:def write_status` needs a client of GitHub: it writes the Status label and reads the issue again.
- `src/devops_cli/roadmap/stores/store.py:def open_pulls` needs a client of GitHub: it reads the open pull requests of the repository.
- `src/devops_cli/roadmap/status_sync.py:def job_holds` needs no checkout, no client and no network: it reads the job record of the Item that the store gave.
- `src/devops_cli/git/branch_form.py:def issue_of_branch` needs no checkout, no client and no network: it reads the head branch text only.
- `src/devops_cli/roadmap/planned.py:77:def planned_changes_at(source: Path, rev: str, default: str, *, operation: str) -> PlannedChanges:` needs a checkout of the repository and runs git, so the release does not call it and takes the plan-merged fact from the record.
- The first checks against the real system are `uv run devops ci test tests/roadmap/test_roadmap_claim.py`, then `uv run devops ci test tests/invariants/test_roadmap_workflow_doc.py`.
- The needed failure classes are `test`, `lint` and `types`; the programs `uv`, `devops`, `pytest` and `git` are in the runner image, none is `NOT_IN_RUNNER`, and the pod settings `readOnlyRootFilesystem: true` and `runAsNonRoot: true` apply.

## Existing Tool Considered

No open, maintained tool or library covers the Status labels of this repository's roadmap, so the change builds the release caller on the writer that already exists: about 3k tokens to build, 1k to keep and 1k to fix, and 1 hour.

## Dependencies

- Pull request #4849 changes src/devops_cli/lang/en/messages.py; this change adds no message there, so the two merge without a conflict.
- Pull request #5198 changes docs/ROADMAP_WORKFLOW.md and src/devops_cli/lang/en/messages.py; this change edits the claim table and the record-key table of docs/ROADMAP_WORKFLOW.md and adds no message there.
