# Proposal: #6597

## Why

Tracker #5223 sets the rule for tool pass-through commands, while its child issues depend on a central pass-through registry and an accepted architecture decision record (#6597). Neither the registry nor the ADR exists yet in the tree, so downstream work lacks typed tool contracts, owned and refused option maps, MCP allowlists, paging costs, and the never-wrapped verb list.

## What Changes

- Add MADR 4 record `docs/adr/0037-tool-commands-mirror-and-pass-through-options.md` recording the 2026-11-12 owner request from #5223: a command that runs a CLI tool takes the command names and options of that tool and forwards arguments through, and a command for an API tool takes the names of the API route.
- Regenerate `docs/adr/README.md` so the index lists ADR `0037`.
- Add `src/devops_cli/core/passthrough.py` defining `PassthroughEntry`, `OwnedOption`, `McpOptionRule`, `PageRule`, `NEVER_WRAPPED` (`pr merge`, `auth`, `secret set`, `repo delete`, `release`), and `REGISTRY` containing the `gh run list` entry (`devops gh run list`, `run_gh`, `read` mode, owned and refused options, MCP allowlist with arity and caps, positive run cost, `-L`/`--limit` page rule, and positive timeout).
- Add test suite `tests/core/test_passthrough.py` covering registry fields, never-wrapped exclusion, CLI command resolution, cost/page/timeout bounds, and MCP allowlist completeness.

## Capabilities

### New Capabilities
- `tool-passthrough-registry`: Declarative registry contract for tool pass-through commands, never-wrapped CLI verbs, and the governing ADR rule.

## Impact

- Single pull request touching `src/devops_cli/core/passthrough.py`, `docs/adr/0037-tool-commands-mirror-and-pass-through-options.md`, `docs/adr/README.md`, and `tests/core/test_passthrough.py`.
- Leaves existing CLI wrappers and MCP generators untouched until downstream items wire them to `REGISTRY`.

## Feasibility

Confirmed on `origin/main` against the codebase and live `gh` help output:
- `docs/adr/` ends at `0036`, so `0037` is the next free ADR number (`0035` and `0036` are already merged).
- `src/devops_cli/core/passthrough.py` does not yet exist.
- `devops_cli.github.rate_limiter.run_gh` and `devops gh run list` exist and resolve cleanly in `resolve_devops_argv`.
- `gh run list --help` confirms `--repo`/`-R`, `--limit`/`-L`, `--branch`/`-b`, `--workflow`/`-w`, `--status`/`-s`, `--json`, and `--jq`/`-q`.

## Existing Tool Considered

No maintained library holds per-entry `devops` alias paths, `run_gh` rate-limit pacing, owned and refused CLI flags, MCP arity/cap allowlists, and never-wrapped verb policies; the alternatives check on #6597 recorded `none`. This change builds `src/devops_cli/core/passthrough.py` and ADR `0037` (~80k tokens and 1.5 engineer-days across the registry contract, ~10k tokens per year to keep and fix) and deletes no code.
