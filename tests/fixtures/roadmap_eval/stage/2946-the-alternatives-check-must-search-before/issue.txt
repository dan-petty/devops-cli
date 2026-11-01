### What happened

The check lets the model decide whether to search. Over 14 days it searched about 4 times and returned `not-applicable` every time, including for a feature that integrates two products.

### What should happen

- A fixed rule, not the model, names the classes of item that skip the search: the Conventional Commit types `test`, `docs`, `refactor`, `chore`, `ci` and `perf`, and a fix of an internal defect with a stack trace and no new capability. The verdict for those is `not-applicable` with the class as the reason, with no model call.
- Every other item must run at least one search before the check accepts any verdict. A reply that gives a verdict with no search is rejected, as a reply that gives `not-applicable` after a tool ran is rejected today, and the model gets one turn to search.
- The classes live in one constant list with a test.

### Evidence (2026-10-31)

- `devops_cli_firecrawl_searches_total`: about 4 searches in 7 days. `devops_cli_roadmap_alternatives_total` over 14 days: only the verdict `not-applicable` (about 34 checks), never `covers`, `partly` or `none`.
- The comments on #886, #1082 and #1329 read "Alternatives check: not-applicable. Tool: none found" with no reason and no queries. #1082 (argo cd points to gitea for git and container registries) is a plausible case for open tools.
- The row checks at most 5 items a day (`roadmap.alternatives.limit`); `dan-petty/devops-cli` has 141 open issues.
- The row for `devops-cli` failed 3 rounds on 2026-10-30 at 00:10 UTC (a `UnexpectedModelBehavior` stop, a reply that gave `not-applicable` after a tool ran, and the then-500 GitHub requests an hour budget), so it was suspended. A plan run on 2026-10-31 stopped again on #1359 (`UnexpectedModelBehavior`).
- AGENTS.md rule 3 says to use an open tool before building. This check is the part of the project that asks the question for every item.

Tracker: #2908 (one issue workflow). Owner request of 2026-10-31: confirm that all issues are vetted for open alternatives.

### Acceptance criteria

- [ ] A table test covers each class with no model call and the reason in the comment.
- [ ] A scripted model that answers a `feat` item without a search gets one more turn, and its second answer without a search ends as a failed check for that item (see the issue on skipping a failed item).
- [ ] The Firecrawl counter rises for a `feat` item in a replay.
- [ ] `uv run devops ci` passes.

<!-- devops-roadmap-refine:start -->
<!-- checked-at: sha=91a971ee079e4f759b6ac681eace9a7c4ab8e54b -->
## Proposed design

### Problem statement
The alternatives check lets the model decide whether to search for open tools. Over 14 days it searched about 4 times and returned not-applicable every time, even for items that integrate two products. A fixed rule must name the classes of item that skip the search, and every other item must run at least one search before the check accepts any verdict.

### Acceptance criteria

### Requirement: Skip-class table test
A table test SHALL cover each skip class with no model call and the class name in the comment.

#### Scenario: Each skip class produces not-applicable without a model call
- **WHEN** The check runs on an item whose type is test, docs, refactor, chore, ci, or perf, or whose body is a fix of an internal defect with a stack trace and no new capability
- **THEN** The verdict is not-applicable, the comment names the class as the reason, and no model call is made

### Requirement: Search-before-verdict enforcement
The check SHALL reject a reply that gives a verdict with no search for a non-skip item, and SHALL give the model one turn to search.

#### Scenario: A scripted model answers a feat item without a search
- **WHEN** The model returns a verdict with no search recorded for a feat item
- **THEN** The check rejects the reply, gives the model one turn to search, and a second answer without a search ends as a failed check for that item

### Requirement: Firecrawl counter rises in replay
The Firecrawl search counter SHALL rise for a feat item in a replay.

#### Scenario: A replay of a feat item triggers a search
- **WHEN** The check runs on a feat item in a replay and the model performs a search
- **THEN** devops_cli_firecrawl_searches_total increases by at least 1

### Requirement: CI passes
The command uv run devops ci SHALL pass.

#### Scenario: Full CI run on the change
- **WHEN** A developer runs uv run devops ci on the branch
- **THEN** All checks pass with no failures

### Existing Tool Considered
No check has run. No open, maintained tool or library covers the need to enforce a search-before-verdict rule inside the devops-cli alternatives check. The project builds this logic itself. The written cost is the tokens to build, keep and fix the constant list, the classification function, the search-enforcement guard, and the table and replay tests, plus the elapsed time to implement and debug them.

### Key questions
- **Which Conventional Commit types and item shapes skip the alternatives search?**: The types test, docs, refactor, chore, ci, and perf, and a fix of an internal defect with a stack trace and no new capability. The verdict for these is not-applicable with the class as the reason, with no model call. (best practice) [sources: AGENTS.md, CONTEXT.md]
  - Chosen: Fixed rule names the skip classes. The body records this decision. A fixed rule is deterministic and testable. It removes the model's discretion to skip the search.
  - Rejected: Let the model decide whether to search. Rejected. Over 14 days the model searched about 4 times and returned not-applicable every time. It is not reliable for this gate.
- **Where does the constant list of skip classes live?**: In the alternatives check module as a single named constant, with a table test that covers each class. (best practice) [sources: AGENTS.md]
  - Chosen: Named constant in the alternatives check module. The body says the classes live in one constant list with a test. A constant in the same module as the check keeps the rule and its enforcement together.
  - Rejected: Separate configuration file. Rejected. The list is a fixed rule, not a user setting. A config file adds indirection without benefit.
  - Rejected: Hardcoded in the model prompt. Rejected. The body says a fixed rule, not the model, names the classes. A prompt is not a fixed rule.
- **How is the search-before-verdict rule enforced for non-skip items?**: A reply that gives a verdict with no search is rejected. The model gets one turn to search. A second answer without a search ends as a failed check for that item. (best practice) [sources: AGENTS.md, CONTEXT.md]
  - Chosen: Reject and give one retry turn. The body records this mechanism. It gives the model a chance to search while still enforcing the rule. A second failure ends the check.
  - Rejected: Hard-fail immediately on first no-search reply. Rejected. It gives the model no chance to correct. The body says the model gets one turn to search.
  - Rejected: Warn and continue with the no-search verdict. Rejected. It does not enforce the rule. The body says the reply is rejected.
- **What verdict and comment does a skip-class item receive?**: The verdict is not-applicable. The comment names the class as the reason. No model call is made. (best practice) [sources: CONTEXT.md]
  - Chosen: not-applicable with the class name as the reason. The body records this. It is consistent with the existing not-applicable verdict in CONTEXT.md and gives a person a clear reason.
  - Rejected: Skip with no comment. Rejected. A person cannot audit why the check was skipped. The body says the reason is in the comment.
- **What is the evidence that the current behavior is broken?**: Over 14 days, devops_cli_roadmap_alternatives_total shows only the verdict not-applicable (about 34 checks), never covers, partly, or none. devops_cli_firecrawl_searches_total shows about 4 searches in 7 days. Comments on #886, #1082, and #1329 read not-applicable with no reason and no queries. [sources: docs/TELEMETRY.md:81, k8s/README.md:609]

### Fit
Fits in one pull request.

### Suspected block
None.

### Dependencies
None.
<!-- devops-roadmap-refine:end -->

<!-- devops-roadmap-record {"Effort": "Medium", "Owner": "Agent", "Priority": "P1-High", "Status": "Planned", "Value": "High", "refine.alternatives_asked": null, "refine.block_paths": null, "refine.blocked_by": null, "refine.body_hash": "2e5a260ee9b4462200f87302f43f8109f7dea6d4e37ce46aa284a9986e7e2f47", "refine.failed_body_hash": null, "refine.needs_split": "false", "refine.next_step": "ready", "refine.section_hash": "1a00f16946523f019e6731ec04aa07a3151ad10cf7fcfd5dac23e4f7e159e76a", "stage.branch": "fix/2946-the-alternatives-check-must-search-before", "stage.file_cap": null, "stage.groups": "[[\"Add skip-class constant and classification\", 4477], [\"Enforce search-before-verdict for non-skip items\", 4466], [\"Verify Firecrawl counter rises in replay\", 4411]]", "stage.needs_split": null, "stage.pr": "2958", "stage.ready": "2958", "stage.sha": "228a2c9ebe079cb5217db7777c7d8da1a3c5792b"} -->
