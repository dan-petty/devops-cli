# Proposal

## Why

Issue #2143: The owner decided on 2026-10-24 that a test of `src/` starts no system program and does not read the host. Every test must run the same in the devcontainer and on a stock runner, with no installation and no host modification on the runner. ADR 0007 and `docs/TESTING.md` still allow real programs in tests, such as git in temporary repositories, kubectl offline renderers, bwrap with the `bwrap` mark, and live local tools under `@pytest.mark.live`.

## What Changes

- ADR 0007 (`docs/adr/0007-tests-double-only-process-edges.md`) adds the amendment of 2026-10-24, records the decision date, and names each removed allowance.
- `docs/TESTING.md` drops the "Live test" definition. The "Real" list removes every program. The process runner contract suite becomes the one location for real child processes.
- `docs/TESTING.md` states where each other real tool goes: a recorded contract suite or a `devops ci` row. It defines the bwrap suite as opt-in for a human in the devcontainer.
- The change sets `skip_specs: true` in `.openspec.yaml` because it edits documentation only and changes no command, option, or code behavior.
- This change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- `docs/adr/0007-tests-double-only-process-edges.md`
- `docs/TESTING.md`

## Feasibility

- Inspection of `docs/adr/0007-tests-double-only-process-edges.md` line 18 shows the earlier allowances for git, bwrap, and kubectl offline renderers.
- Inspection of `docs/TESTING.md` line 31 shows the `Live test` definition and line 67 shows programs in the `Real` list.
- Running `rg -in "run for real|live test|bwrap mark" AGENTS.md CONTRIBUTING.md docs src/devops_cli/ai/knowledge_base` confirms where these phrases appear across documentation and instructions.
- Running `uv run pytest tests/invariants/test_agents_md_claims.py` verifies document links and claims remain valid.

## Existing Tool Considered

Markdown documents in Git. No software tool is built.
