### What happened

If the check of one item fails, the row writes the others and then fails, naming the item. After 3 failed rounds in a row the row is suspended until its input changes. On 2026-10-30 one item (`UnexpectedModelBehavior` on #1127) did this to the whole repository.

### What should happen

- A failed check of one item is recorded in the item's job record (the item, the class of error, the time) and the round succeeds. A later round tries the item again after a set number of days, and not in the next round.
- The stop reason uses the tool-call retry reasons of #2875 and the readable provider text of #2922.
- The row fails, and counts toward the 3-round suspension, only when no item could be checked in the round (for example no search key or no model).

### Evidence (2026-10-31)

- `devops_cli_firecrawl_searches_total`: about 4 searches in 7 days. `devops_cli_roadmap_alternatives_total` over 14 days: only the verdict `not-applicable` (about 34 checks), never `covers`, `partly` or `none`.
- The comments on #886, #1082 and #1329 read "Alternatives check: not-applicable. Tool: none found" with no reason and no queries. #1082 (argo cd points to gitea for git and container registries) is a plausible case for open tools.
- The row checks at most 5 items a day (`roadmap.alternatives.limit`); `dan-petty/devops-cli` has 141 open issues.
- The row for `devops-cli` failed 3 rounds on 2026-10-30 at 00:10 UTC (a `UnexpectedModelBehavior` stop, a reply that gave `not-applicable` after a tool ran, and the then-500 GitHub requests an hour budget), so it was suspended. A plan run on 2026-10-31 stopped again on #1359 (`UnexpectedModelBehavior`).
- AGENTS.md rule 3 says to use an open tool before building. This check is the part of the project that asks the question for every item.

Tracker: #2908 (one issue workflow). Owner request of 2026-10-31: confirm that all issues are vetted for open alternatives.

### Acceptance criteria

- [ ] A test with one failing item and four good items ends with a successful round and a record for the failing item.
- [ ] A round in which every item fails still fails.
- [ ] The failed item is tried again after the set time, not before.
- [ ] `uv run devops ci` passes.

<!-- devops-roadmap-refine:start -->
<!-- checked-at: sha=66ed3bf10b95a1c351c5dfdadafe8a9ab2fd7a50 -->
## Proposed design

### Problem statement
The alternatives check row fails the entire round when one item's check fails. After three failed rounds, the row is suspended. One bad item should not block the other items in the round. The fix records the failure in the item's job record, lets the round succeed, and retries the item after a set number of days.

### Acceptance criteria

### Requirement: partial-failure-isolation
A round with one failing item and four good items SHALL succeed and record the failure for the failing item.

#### Scenario: one-of-five-fails
- **WHEN** the alternatives row runs with five items and one item's check raises an error
- **THEN** the round completes successfully, four items have their checks written, and the failing item's job record holds the error class and the time

### Requirement: total-failure-still-fails
A round in which every item fails SHALL fail the row and count toward the three-round suspension.

#### Scenario: all-items-fail
- **WHEN** the alternatives row runs and every item's check raises an error
- **THEN** the row fails and the failure counts toward the three-round suspension

### Requirement: retry-delay
A failed item SHALL NOT be retried before the set number of days has elapsed since its failure.

#### Scenario: retry-before-set-time
- **WHEN** a later round runs before the set number of days since the item's recorded failure
- **THEN** the item is skipped and not checked again

### Requirement: ci-passes
The command `uv run devops ci` SHALL pass on the change.

#### Scenario: full-ci
- **WHEN** the full CI suite runs on the change branch
- **THEN** all checks pass

### Existing Tool Considered
No check has run. No open, maintained tool covers this need. The fix modifies the project's own alternatives row code in the roadmap service. The written cost is the tokens to write the per-item error isolation, the retry scheduling, the stop reason formatting, and the tests, plus the elapsed time to pass `uv run devops ci`.

### Key questions
- **What is the retry interval for a failed item?**: Three days, configurable via `roadmap.alternatives.retry_days`. (best practice) [sources: k8s/README.md:610]
  - Rejected: 1 day (next round). The body says 'not in the next round.' One day is the round interval, so this does not meet the requirement.
  - Chosen: 3 days. More than one round, less than the 30-day recheck interval. Gives the upstream service time to recover. Matches the pattern of a configurable setting.
  - Rejected: 7 days. Too long. The item waits a full week before retry, which delays the owner's request to confirm all issues are vetted.
- **What fields does the failure record contain?**: The item number, the class of error, and the time of the failure. [sources: k8s/README.md:610]
- **What stop reason format does the failure record use?**: The tool-call retry reasons of #2875 and the readable provider text of #2922. [sources: openspec/changes/archive/2026-10-30-2562-refine-warning-reasons/design.md:13, openspec/changes/archive/2026-10-28-2398-refine-investigates-questions/design.md:39]
- **When does the row fail and count toward the three-round suspension?**: The row fails only when no item could be checked in the round, for example when there is no search key or no model. [sources: k8s/README.md:610]

### Fit
Fits in one pull request.

### Suspected block
None.

### Dependencies
#2922
<!-- devops-roadmap-refine:end -->

<!-- devops-roadmap-record {"Effort": "Medium", "Owner": "Agent", "Priority": "P1-High", "Status": "Planned", "Value": "High", "refine.alternatives_asked": null, "refine.block_paths": null, "refine.blocked_by": null, "refine.body_hash": "86e301027f5073fbe442e2683c3a886a0d8ceb96b058ad8b85b2ba38ae1cce9b", "refine.failed_body_hash": null, "refine.needs_split": "false", "refine.next_step": "ready", "refine.section_hash": "20919a33911a7ffac25c892c525af8ac612247f814ac33dfb88eafa3c3aff81a", "stage.branch": "fix/2949-a-failed-alternatives-check-skips-its", "stage.file_cap": null, "stage.groups": "[[\"Add retry_days config and failure record structure\", 4339], [\"Per-item error isolation in the alternatives round\", 4368], [\"Retry delay for failed items\", 4347], [\"Row fails only when zero items are checked\", 4351], [\"Update documentation for the new behavior\", 4400]]", "stage.needs_split": null, "stage.pr": "2976", "stage.ready": "2976", "stage.sha": "f5bf180fddc9846e9ae4095a5706ca3b5c31dada"} -->
