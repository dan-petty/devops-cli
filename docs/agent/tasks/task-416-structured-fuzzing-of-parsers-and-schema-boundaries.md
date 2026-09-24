# Task 416: Structured Fuzzing of Parsers and Schema Boundaries

**Issue**: [#416](https://github.com/dan-petty/devops-cli/issues/416)
**Status**: Backlog
**Milestone**: `v0.2.25`
**Priority**: `priority/p2-medium`
**Scope**: `type/feature`, `scope/cli`, `priority/p2-medium`

---

## 1. Description & Objectives

The failures found by hand this release were nearly all boundary cases in parsing and path handling: `Path.relative_to` accepting `..`, `fnmatch` reading `[host]:port` as a character class, `lstrip("./")` stripping a character set, porcelain output shifted by one stripped space. Each was found by reading code. Each is the kind of input a property test generates in seconds.

#### Key Deliverables:
- Context & Rationale*: The failures found by hand this release were nearly all boundary cases in parsing and path handling: `Path.relative_to` accepting `..`, `fnmatch` reading `[host]:port` as a character class, `lstrip("./")` stripping a character set, porcelain output shifted by one stripped space. Each was found by reading code. Each is the kind of input a property test generates in seconds.
- Deliverable*: Property-based tests over the parsing surfaces — ignore rules, `known_hosts` entries, service URLs, SARIF documents, git porcelain output, review JSON — asserting the invariants those parsers claim rather than specific outputs. Generated corpora persist so a discovered failure becomes a regression case.
- Constraint*: A property test that asserts what the implementation does rather than what the format requires passes forever and finds nothing. Each property has to come from the specification: gitignore(5), the `sshd` manual, SARIF 2.1.0.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
