# Proposal

## Why

Refine sets an item Ready even when the alternatives check wrote no verdict, so a plan can start with no answer to the open-tool question of AGENTS.md rule 3 (#2951). The tracker #2908 names refine as step 2 of the workflow, and the alternatives check is the part of the project that asks that question for every item.

## What Changes

- Refine reads the recorded alternatives check and sets `status/ready` only with a verdict or on a repository whose alternatives check is off (`src/devops_cli/roadmap/refine/refine.py`).
- An item with no verdict waits on the new step `alternatives`, writes the comment `Waiting for the alternatives check to run.`, and the next round takes it once the check records a verdict; the key `alternatives` goes into each of the three maps of `src/devops_cli/lang/en/messages.py` that a step value indexes.
- A refine round writes `status/new` on a Ready item only when a job wrote that label, so a `status/ready` label that a person set stays (`src/devops_cli/roadmap/refine/refine.py`).
- A new `tests/roadmap/refine/test_roadmap_refine_alternatives_gate.py` proves the gate, the wait, the rendered report and the person-set Ready label.
- The refine tests that reach Ready on a public repository give their items the recorded check that the alternatives row writes.
- Step 2 of `docs/ROADMAP_WORKFLOW.md` names the gate, and `uv run devops ci` runs the whole gate on the branch.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-refine/alternatives`: A recorded verdict gates Ready, A person's Ready label stays through a round, The wait for a verdict ends when the check writes one, The workflow document names the gate

## Impact

- Code: `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/lang/en/messages.py`
- Documents: `docs/ROADMAP_WORKFLOW.md`
- Tests: `tests/roadmap/refine/test_roadmap_refine_alternatives_gate.py`, `tests/roadmap/refine/test_roadmap_refine_investigation.py`, `tests/roadmap/refine/test_roadmap_refine_deferred.py`

## Feasibility

- The premise is confirmed: the probes say "The path `docs/ROADMAP_WORKFLOW.md` is a file of the staging commit." and "The path `src/devops_cli/roadmap/alternatives.py` is a file of the staging commit.", so the workflow document and the alternatives job that the issue cites are in the staged tree.
- The probes say "The path `alternatives.verdict` is no file of the staging commit. No commit in the history deleted or renamed it.", so the issue names a job-record key and not a path; `src/devops_cli/roadmap/stores/store.py:219:VERDICT = "alternatives.verdict"` defines it under `src/devops_cli/roadmap/stores/store.py:class AlternativesRecordKey`.
- `read_file` of `src/devops_cli/roadmap/refine/refine.py` lines 2596-2690 showed the round reads the recorded check for its request but not for readiness, and `src/devops_cli/roadmap/refine/refine.py:2639:is_ready = check_ready(proposal, open_questions, blockers)`, so the gate is absent today.
- `read_file` of `src/devops_cli/roadmap/refine/refine.py` lines 3283-3325 showed `src/devops_cli/roadmap/refine/refine.py:3309:write_status(store, r.item, StatusFacts(needs_refine=True), marks=marks, body=r.new_body)`, so a round reverts a Ready label that a person set, which is the second criterion.
- `read_file` of `src/devops_cli/roadmap/status_sync.py` lines 160-190 showed `src/devops_cli/roadmap/status_sync.py:181:def owns_status(item: Item) -> bool` and its rule `src/devops_cli/roadmap/status_sync.py:187:and item.job_record.get(ItemField.STATUS) == item.status`, which tells a job's label from a person's. The plan changes `src/devops_cli/roadmap/refine/refine.py` alone for that guard and imports the function.
- `read_file` of `src/devops_cli/roadmap/refine/refine.py` lines 222-240 showed `src/devops_cli/roadmap/refine/refine.py:231:from devops_cli.roadmap.status_sync import StatusFacts, write_status`, the import that the person-set guard extends.
- `read_file` of `src/devops_cli/roadmap/stage/stage_registry.py` lines 117-131 showed `src/devops_cli/roadmap/stage/stage_registry.py:126:if any(entry.token in text for text in texts) or any(entry.token in path for path in paths):`, so the registry gate matches a token in any task text. `read_file` of `tests/roadmap/test_roadmap_limit_classes.py` lines 30-60 showed `tests/roadmap/test_roadmap_limit_classes.py:47:("prefix", "CONST_ROADMAP_", "tests/roadmap/test_roadmap_limit_classes.py"),`. The plan adds no constant and no counted item, so no group changes that table, and the plan cites the symbol `src/devops_cli/roadmap/refine/refine.py:def _apply_refined` and names no constant in a task text.
- `read_file` of `src/devops_cli/roadmap/refine/refine.py` lines 1005-1035 showed `src/devops_cli/roadmap/refine/refine.py:def web_search_of` gives `on` true only for a public repository with a search provider, and `src/devops_cli/roadmap/refine/refine.py:2621:tools = InvestigationTools(source=source, sha=sha, web=web.on, pages=pages)` shows the round already holds `web`, so the gate is exempt exactly when the alternatives row is off.
- `read_file` of `src/devops_cli/roadmap/refine/refine.py` lines 2060-2150 showed the `match step` of `def _still_waiting` and `src/devops_cli/roadmap/refine/refine.py:2077:def _settled_wait(item: Item, step: NextStep) -> WaitingItem:`, so the new step needs one case there.
- The review finding is confirmed and the plan answers it: `search_code` of `step.value` gave `src/devops_cli/roadmap/refine/refine.py:1450:template = texts.refine_step_comments[step.value]`, `src/devops_cli/roadmap/refine/refine.py:2318:return texts.refine_left_waits[waits.step.value].format(details=shown).strip()` and `src/devops_cli/roadmap/refine/refine.py:3480:return [texts.refine_step_headings[step.value], *lines] if lines else []`, so the new step needs an entry in three maps, not two, and the first group adds each one and tests each one.
- `read_file` of `src/devops_cli/lang/en/messages.py` lines 2728-2760, 2783-2794 and 2855-2866 showed the three maps that a step value indexes: `src/devops_cli/lang/en/messages.py:2733:refine_step_comments: dict[str, str] = field(`, `src/devops_cli/lang/en/messages.py:2783:refine_left_waits: dict[str, str] = field(` and `src/devops_cli/lang/en/messages.py:2855:refine_step_headings: dict[str, str] = field(`, and none of them holds an `alternatives` key.
- `read_file` of `src/devops_cli/roadmap/refine/refine.py` lines 564-600 showed `src/devops_cli/roadmap/refine/refine.py:592:recorded = item.job_record.get(AlternativesRecordKey.VERDICT)` and `src/devops_cli/roadmap/refine/refine.py:593:if block is None or not recorded:`, so `def recorded_check` is the gate's read and a deleted block is no check.
- `read_file` of `src/devops_cli/roadmap/refine/refine.py` lines 651-671 showed `src/devops_cli/roadmap/refine/refine.py:657:if check is None or check.verdict is not Verdict.COVERS or not check.tool:`, so a `covers` verdict is the one verdict that asks a person today, and `docs/CLUSTER.md` says the same of a `covers` verdict.
- `read_spec` of `roadmap-refine/alternatives` listed six requirement names, among them `The request holds the recorded check for alternatives` and `A covers verdict is a question that only a person answers`; the plan adds names that no requirement of the capability holds.
- The staged value of the constant the plan relies on is `src/devops_cli/config/constants.py:3749:CONST_ROADMAP_STATUS_READY: Final[str] = "Ready"`; the plan sets no bound of a constant and adds no constant.
- `src/devops_cli/roadmap/status_sync.py:def write_status` needs a client of GitHub: it writes the Status label and reads the issue again.
- `src/devops_cli/roadmap/refine/refine.py:def web_search_of` needs a client of GitHub: it reads the visibility of the repository.
- `src/devops_cli/roadmap/refine/refine.py:def recorded_check` needs no checkout, no client and no network: it reads the item that the round holds.
- `src/devops_cli/roadmap/status_sync.py:def owns_status` needs no client and no network: it reads the item that the round already holds.
- `src/devops_cli/roadmap/refine/refine.py:def _still_waiting` needs a client of GitHub on its other waits, which read the comments and the blockers; its new `alternatives` case reads the item alone.
- The plan introduces no command and no verify program: the verifies are `uv run devops ci test` and `uv run devops ci`, whose programs `uv`, `python` and `pytest` are in the runner image, under the pod settings `runAsNonRoot: true` and `readOnlyRootFilesystem: true`. The plan adds no failure class.
- The first checks against the real system are `uv run devops ci test tests/roadmap/refine/test_roadmap_refine_alternatives_gate.py`, then `uv run devops ci test tests/roadmap/refine`, then `uv run devops ci`.

## Existing Tool Considered

No open, maintained tool covers this. Probot, OPA and the policy engines act on GitHub events and resource payloads and know nothing of the alternatives record or of refine's Status write. The gate, the wait step and the person-set guard are about 120 lines of product code and about 150 lines of tests: about 30k tokens to build, about 5k tokens a year to keep, about 10k tokens for a fix, and about 2 hours elapsed.

## Dependencies

- `devops_cli_roadmap_alternatives_total`: the other senders are `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/telemetry/instruments.py`, `docs/CLUSTER.md`, `docs/TELEMETRY.md` and the archived changes of #2652, #2946, #2947, #3505, #4054 and #4661; this change adds no count and no verdict to that metric.
