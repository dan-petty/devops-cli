### Problem or Motivation

When `devops roadmap refine` evaluates an issue that has outstanding questions or functionality that cannot be implemented as written, refinement blocks the whole item or sends it to `NextStep.PERSON`. Workable subsets of functionality remain delayed behind questions or unworkable parts.

### Proposed Solution & Architectural Design

Update `devops roadmap refine` and its refinement prompt (`src/devops_cli/ai/tasks/roadmap_refine_proposal.md`):
- When an issue includes parts that cannot be implemented as written or have unresolved questions, remove those parts from the core proposal.
- File separate issues on the roadmap for investigation or subsequent implementation of the removed functionality.
- Allow the remaining workable scope of the original issue to proceed toward `Ready`.
- Record links between the original issue and any newly created investigation or implementation issues.

### Target Subsystem

SDLC, Git & PR Governance

### Existing Tool Considered

`devops roadmap intake` and the existing roadmap store handle issue creation and board updates. Refining the prompt and orchestrator extends built-in functionality without new external dependencies.

### Standards Compliance

- [x] I confirm this proposal aligns with AGENTS.md engineering principles (cyclomatic complexity <= 10, nesting <= 5, zero bare exceptions, tests that cover the changed lines).
- [x] I am willing to submit a pull request implementing this feature with accompanying tests.

<!-- devops-roadmap-refine:start -->
<!-- checked-at: sha=d739a472dcfc7c8394513e4afcaad359b5a0fbd4 -->
## Proposed design

### Problem statement
When `devops roadmap refine` finds an issue with unworkable parts or unresolved questions, it blocks the whole item. Workable subsets remain delayed behind the blocked parts. This change lets refine remove unworkable scope into new issues. The remaining workable scope then proceeds toward Ready.

### Acceptance criteria
- Criterion 1: The refine prompt instructs the model to identify unworkable scope and propose it as separate issues.
  Verification: Read the updated `src/devops_cli/ai/tasks/roadmap_refine_proposal.md` and confirm it contains instructions for identifying and removing unworkable scope into new issues.
- Criterion 2: The orchestrator creates a new issue for each split-off part of the scope.
  Verification: Run `devops roadmap refine` on a test issue with unworkable parts and confirm new issues appear on the roadmap.
- Criterion 3: The remaining workable scope of the original issue proceeds toward Ready.
  Verification: Run `devops roadmap refine` on a test issue with mixed scope and confirm the original issue moves to Ready status.
- Criterion 4: Links are recorded between the original issue and each newly created issue.
  Verification: After a refine run that splits scope, check the issue comments or cross-references for links to the new issues.
- Criterion 5: Tests cover the new scope-splitting behavior.
  Verification: Run `uv run pytest` and confirm tests for the split behavior pass.

### Key questions
- **How does the refine response communicate scope splitting to the orchestrator?**: Extend the refine response with a field that lists each split-off scope item with its title and body. The orchestrator reads this field and calls the existing intake path to create each new issue. (proposed) [sources: src/devops_cli/ai/tasks/roadmap_refine_proposal.md]
- **What mechanism creates the new issues on the roadmap?**: The existing `devops roadmap intake` command and the roadmap store handle issue creation and board updates. The orchestrator reuses this path for split-off issues. [sources: CONTEXT.md]
- **What status does the original issue receive after scope is split off?**: The original issue proceeds toward Ready with its remaining workable scope. The split-off parts become separate issues in the backlog. (proposed) [sources: CONTEXT.md]

### Fit
Fits in one pull request.

### Suspected block
None.

### Dependencies
None.
<!-- devops-roadmap-refine:end -->

<!-- devops-roadmap-record {"Effort": "Medium", "Owner": "Agent", "Priority": "P2-Medium", "Status": "Planned", "Value": "Medium", "refine.block_paths": null, "refine.blocked_by": null, "refine.body_hash": "647b7fce01ce382f0fd19724c721d86485024a02b5ead130b45db426d3619819", "refine.failed_body_hash": null, "refine.needs_split": "false", "refine.next_step": "ready", "refine.section_hash": "8e756f09e08b61fb1194879d4457ca6c8e5e6c4c0e40062a4e030d2c17eeac6c", "stage.branch": "feat/2423-split-unworkable-or-unanswered-scope-during", "stage.file_cap": null, "stage.groups": "[[\"Add scope-splitting instructions to the refine prompt\", 3271], [\"Process split_issues in the refine orchestrator\", 3264], [\"Add integration test for the full scope-splitting flow\", 3251]]", "stage.needs_split": null, "stage.pr": "2989", "stage.ready": "2989", "stage.sha": "5cf0eada5b9273dd58b2a6b674a216862dffb37e"} -->
