### Problem or Motivation

Agents currently have instructions to return unworkable items to New, but no explicit instruction to close issues as rejected when newer issues or code changes have superseded their functionality.

### Proposed Solution & Architectural Design

Update Rule 2 in `AGENTS.md` and `src/devops_cli/templates/AGENTS.md.j2` to instruct agents to close issues as rejected if their functionality has been superseded by newer issues or code changes. Add unit tests asserting this behavior and verifying character limits.

### Target Subsystem

SDLC, Git & PR Governance

### Existing Tool Considered

Built-in agent instructions (`AGENTS.md`) and generator templates.
