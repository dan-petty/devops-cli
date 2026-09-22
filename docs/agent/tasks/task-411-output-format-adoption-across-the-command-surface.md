# Task 411: Output Format Adoption Across the Command Surface

**Issue**: [#411](https://github.com/dan-petty/devops-cli/issues/411)
**PR**: None (Draft)
**Status**: Backlog
**Milestone**: `v0.2.23`
**Priority**: `priority/p2-medium`
**Scope**: `type/feature`, `scope/cli`, `priority/p2-medium`

---

## 1. Description & Objectives

v0.2.22 built the join point -- `emit_serialized` renders a payload in any supported format, YAML output is portable rather than Python-tagged, and the console wrapper no longer defeats Rich's colour negotiation. Adoption is the remainder. Of 306 registered commands, 53 expose `--json`, 17 expose `--format`, and the 10 that route through the join point get YAML at no cost. The rest each emit their own `json.dumps`, so a new format still means editing every one of them.

#### Key Deliverables:
- Context & Rationale*: v0.2.22 built the join point -- `emit_serialized` renders a payload in any supported format, YAML output is portable rather than Python-tagged, and the console wrapper no longer defeats Rich's colour negotiation. Adoption is the remainder. Of 306 registered commands, 53 expose `--json`, 17 expose `--format`, and the 10 that route through the join point get YAML at no cost. The rest each emit their own `json.dumps`, so a new format still means editing every one of them.
- Deliverable*: Move the remaining `--json` commands onto the join point, then add `--format` where a command has a serialisable result.
- Constraint*: "100% of subcommands" is the wrong target and was the original framing. An interactive chat, a port-forward daemon and a TUI have no result to serialise, and giving them a `--format` flag that emits an empty object is worse than not offering one. The deliverable is every command whose output is a value, which has to be enumerated rather than assumed.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
