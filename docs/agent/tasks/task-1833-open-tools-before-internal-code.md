# Task: Building Internal Code Instead of Using an Open Tool Needs a Written Cost (#1833)

**Issue**: [#1833](https://github.com/dan-petty/devops-cli/issues/1833)
**Scope**: scope/github
**Feasibility**: AGENTS.md section 1 held the rule as one sentence inside the "Modern Python Ecosystem" bullet ("Avoid custom workarounds when standard library or established open-source tools exist"), and the feature request form asked for "Alternatives Considered" as an optional field. Neither asked for the choice to be justified. The release workflow shows what that cost: about 3,000 lines in `src/devops_cli/release/`, `src/devops_cli/roadmap/close.py` and `src/devops_cli/commands/release.py`, a 403-line `release.yml`, 16 test files, and 94 issues and 138 merged pull requests with release, changelog, cut or fragment in the title on 2026-10-22. AGENTS.md had 293 characters of headroom under `CONST_AGENTS_MD_MAX_CHARS` (40,000), and has 81 after this change, which `tests/test_agents_md_claims.py` enforces.

## Description

- [x] AGENTS.md has a top-level bullet, "Open Tools Before Internal Code", that replaces the buried sentence. Before building a capability the author names the open tool or library that covers it. Building instead needs a written cost in the issue or pull request: the tokens to implement it, to maintain it and to fix it until it matches the tool, plus the elapsed time. A plan that prescribes a build is a proposal.
- [x] The feature request form requires "Existing Tool Considered" in place of the optional "Alternatives Considered", and asks for the same cost.
- Not done: the roadmap refine prompts and the builder and reviewer briefs ask the same question. They change the structured reply of the in-cluster refine job, so they follow with the OpenSpec work that realigns refine.

## Acceptance Criteria

- [x] AGENTS.md has the bullet, the old sentence is gone, and `tests/test_agents_md_claims.py` passes.
- [x] The feature request form requires "Existing Tool Considered" with the cost prompt.
- [x] `devops ci` passes.
