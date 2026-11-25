---
status: accepted
date: 2026-11-12
decision-makers: [owner]
issue: 6597
tracker: 5223
body-hash: aa84a5f1276d67e952af129bd45e9ff825f490ffa27cd931de6e1cfbb3ea54af
---

# Tool commands mirror and pass through options

## Context and Problem Statement

Wrapper subcommands currently re-declare small subsets of underlying CLI flags under custom names, such as `-n` for `gh`'s `-L` on workflow runs or custom `--format` flags instead of `--json` and `--jq`. Every missing flag triggers usage errors across agents and people whenever a real tool option is passed. On 2026-11-12 in #5223, the owner requested that commands executing another CLI tool mirror that tool's command names and options and forward arguments through, and that commands for API-based tools take the names of the API route.

## Decision Drivers

- Keep CLI command and option names aligned with upstream tool documentation so agents and developers do not guess wrapper-specific renames.
- Enforce security, repository scoping, rate-limit pacing, and MCP safety bounds explicitly in one registry rather than scattering ad-hoc guards across subcommands.
- Keep dangerous or out-of-policy operations (`pr merge`, `auth`, `secret set`, `repo delete`, `release`) unexposed.

## Considered Options

- **Central pass-through registry (`REGISTRY`) with mirrored tool verbs, options, and API route names**: chosen.
- **Per-command hand-wrapped Typer option subsets**: rejected, because wrappers drift behind upstream tool releases and produce high usage-error rates on valid tool flags.
- **Unvalidated pass-through with no registry metadata**: rejected, because callers still need explicit owned-option validation, refused-option blocking, rate-limit cost accounting, timeouts, and MCP allowlists.

## Decision Outcome

Chosen option: "Central pass-through registry (`REGISTRY`) with mirrored tool verbs, options, and API route names", because a command that runs a tool takes the command names and the options of the tool and passes its arguments through, while a command of an API-based tool takes the names of the API route. `src/devops_cli/core/passthrough.py` stores one entry per tool path with `devops_paths`, `runner`, read/write `mode`, `owned_options`, `refused_options`, `mcp_allowlist`, `run_cost`, `page_rule`, and `timeout`, alongside `NEVER_WRAPPED`.

### Consequences

- Good, because downstream commands and MCP wrappers share one authoritative table of owned options, refused options, paging costs, and timeouts.
- Bad, because each new pass-through command needs a tested entry in `REGISTRY` and explicit MCP allowlist caps before exposure.

### Confirmation

`tests/core/test_passthrough.py` verifies registry entries, never-wrapped exclusions, CLI command resolution, paging rules, timeouts, and MCP allowlists; `tests/invariants/test_adr_records.py` and `uv run devops docs check` verify this record and its index row.

## More Information

- [Passthrough registry](../../src/devops_cli/core/passthrough.py)
- Tracker #5223 and implementation issue #6597

## Status History

- 2026-11-12: Recorded the owner request from #5223 in #6597.
