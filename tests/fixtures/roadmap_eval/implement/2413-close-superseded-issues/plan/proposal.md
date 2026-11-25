# Proposal

## Why

Issue #2413: When a new issue or code change supersedes an existing issue, agents lack instruction to close the superseded issue as rejected.

- Agents continue work on obsolete issues when the instruction does not tell them to close them as rejected.
- Rule 2 of `AGENTS.md` directs agents to return an issue to `New` when its premise fails, but does not state the rule for superseded issues.
- `src/devops_cli/templates/AGENTS.md.j2` generates `AGENTS.md`, and both must stay in sync and under `CONST_AGENTS_MD_MAX_CHARS` (6,500 characters).

## What Changes

- Update Rule 2 of `AGENTS.md` and `src/devops_cli/templates/AGENTS.md.j2` to instruct agents to close issues as rejected if newer issues or code changes supersede them.
- Adjust surrounding prose in `AGENTS.md` to keep the character count within `CONST_AGENTS_MD_MAX_CHARS`.
- Add test coverage in `tests/test_instruction_generator.py` and `tests/test_agents_md_claims.py` to verify the rule and the template content.
- The change alters no commands or public APIs, sets `skip_specs: true` in `.openspec.yaml`, and fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Documents: `AGENTS.md` and `src/devops_cli/templates/AGENTS.md.j2`.
- Tests: `tests/test_instruction_generator.py` and `tests/test_agents_md_claims.py`.

## Feasibility

- Verified against `AGENTS.md` and `src/devops_cli/templates/AGENTS.md.j2`. Adding the rule and trimming non-essential prose keeps `AGENTS.md` at 6,480 characters, under the 6,500 limit.
- Verified test suite passes with `pytest tests/test_instruction_generator.py tests/test_agents_md_claims.py`.

## Existing Tool Considered

Built-in template rendering and test suites cover this change. No external library is needed.
