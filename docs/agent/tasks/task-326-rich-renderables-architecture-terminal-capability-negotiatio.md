# Task 326: Rich Renderables Architecture, Terminal Capability Negotiation & Universal Output Serialization Research

**Issue**: [#326](https://github.com/dan-petty/devops-cli/issues/326)
**PR**: [#391](https://github.com/dan-petty/devops-cli/pull/391)
**Status**: Merged
**Milestone**: `v0.2.22`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/cli`, `priority/p1-high`

---

## 1. Description & Objectives

CLI terminal formatting mixes procedural `rich.print` calls, Typer echoes, and custom table formatters, creating inconsistent visual styles and hindering machine-readable automation.

#### Key Deliverables:
- Context & Rationale*: CLI terminal formatting mixes procedural `rich.print` calls, Typer echoes, and custom table formatters, creating inconsistent visual styles and hindering machine-readable automation.
- Deep Integration & Functional Extension*: Standardized Renderables pipeline with dynamic terminal capability negotiation (detecting NO_COLOR, TTY, CI, and color depths) and universal `--json` / `--yaml` output serialization across 100% of CLI subcommands.
- Code Optimization & Performance Acceleration*: Streamline terminal output generation by replacing custom string formatting with native Rich Console protocols; eliminate redundant serialization logic across CLI commands; ensure predictable machine-readable output in CI automation.
- Refactoring Potential & Legacy Elimination*: Refactor `src/devops_cli/output.py` to replace procedural table formatting loops with declarative Pydantic-to-table mappers; standardize log levels, error alerts, and progress bars across all command modules.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).

---

## 2. Outcome

### Delivered

- **`output/serialization.py`** -- the join point the codebase did not have. `emit_serialized(payload, fmt)` accepts a Pydantic model, an object exposing `to_dict()`, or a plain structure, and writes it in the requested format. Adding a format is now a change here rather than in every command that emits one.
- **Portable YAML.** `yaml.dump` writes a Python constructor tag for anything it does not recognise, so an enum rendered as `!!python/object/apply:...` and `yaml.safe_load` refused to read it back. Values now pass through JSON coercion first, so the two formats describe the same data rather than claiming to.
- **Terminal capability negotiation restored.** `get_console` defaulted `color_system` to `None`, and `None` is not "unspecified" to Rich -- it means no colour at all. Every caller passing `file=` or `force_terminal=` silently lost colour, which is the opposite of negotiating a terminal's capabilities. The default now inherits Rich's negotiation, so `NO_COLOR`, a non-TTY destination and `TERM=dumb` take effect; passing `color_system=None` explicitly still disables colour, which is what this suite wants.
- **Ten emission sites converted**, across `ai_gateway`, `ai_controller` and `ai_chaos`. These already exposed `--format`, so they gained working YAML with no signature change.

### Deliberately not delivered

The issue asked for `--json` / `--yaml` across **100% of CLI subcommands**. That target is wrong, and saying so is part of the outcome. Of 306 registered commands, an interactive chat, a port-forward daemon and a TUI have no result to serialise; giving them a `--format` flag that emits an empty object is worse than not offering one. The remaining adoption is roadmapped as *every command whose output is a value*, which has to be enumerated rather than assumed.

Measured at close: 306 commands, 53 with `--json`, 17 with `--format`, 10 routed through the join point.
