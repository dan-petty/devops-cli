# Design

## Decisions

1. **Use ADR number `0037` with MADR 4 front matter and body hash.**
   `docs/adr/0035-*` and `docs/adr/0036-*` are already committed on `origin/main`, so `0037` is the lowest unused number (`docs/adr/README.md:182-183`). Front matter records `status: accepted`, `date: 2026-11-12`, `decision-makers: [owner]`, `issue: 6597`, `tracker: 5223`, and `body-hash` validated by `tests/invariants/test_adr_records.py`.

2. **Represent entries as immutable frozen dataclasses in `REGISTRY`.**
   `PassthroughEntry`, `OwnedOption`, `McpOptionRule`, and `PageRule` use `@dataclass(frozen=True)` with explicit field types so callers and tests inspect typed attributes offline without runtime YAML loading or mutable shared dicts (`src/devops_cli/github/rate_limiter.py:1888`, `src/devops_cli/core/process.py:1048`).

3. **Bind `gh run list` to `run_gh` and register only `devops gh run list`.**
   `gh run list` runs through `run_gh` so GitHub pacing, caching hooks, and secret masking stay intact (`src/devops_cli/github/rate_limiter.py:1888`). `devops_paths` lists only `("devops gh run list",)` because `devops run list` is not registered in `src/devops_cli/commands/gh.py` or `main.py` yet, and every entry path must resolve via `resolve_devops_argv`.

4. **Constrain MCP allowlist entries to owned options with arity and caps.**
   Every key in `mcp_allowlist` must be present in `owned_options`, and every `McpOptionRule` specifies non-negative `arity` and a positive `cap` (`max_value` or `max_length`). `refused_options` lists unsafe interactive or foreign-host flags (`--web`, `--hostname`).

## Rejected alternatives

- **Use ADR `0035` or `0036`.** Rejected: both numbers already exist in `docs/adr/` (`docs/adr/README.md:182-183`), and `tests/invariants/test_adr_records.py` fails on duplicate numbers.
- **Use `TypedDict` or untyped dicts for `REGISTRY` entries.** Rejected: lacks immutability guarantees and runtime attribute guarantees on `page_rule` and `mcp_allowlist`.
- **Include unregistered alias `devops run list` in `devops_paths`.** Rejected: `resolve_devops_argv(["run", "list"])` fails until a separate change registers a top-level `run` group.
- **Bind `gh run list` to `run_subprocess`.** Rejected: bypasses `run_gh` GitHub rate limiting (`src/devops_cli/github/rate_limiter.py:1888`).
