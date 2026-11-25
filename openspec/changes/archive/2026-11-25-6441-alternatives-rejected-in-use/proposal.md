# Proposal: #6441

## Why
Issue #6441 reports false `rejected` verdicts from the alternatives check on tools that the project already uses, and even on the repository itself:

- `rejects()` matches tool names inside Markdown link targets (`_spans()` in `src/devops_cli/roadmap/adr.py`) and matches single-word modifiers such as `Kubernetes Lease`, `` `gh` CLI ``, or packaging methods such as `bundling the CodeQL CLI`.
- `_verdict_of()` in `src/devops_cli/roadmap/alternatives.py` checks `reply.adr` before checking whether the candidate tool is the item's own repository.

## What Changes
- Parse each `Considered Options` bullet in `src/devops_cli/roadmap/adr.py` to isolate the option subject title, strip Markdown link targets before matching, ignore prepositional modifiers and packaging-method clauses (`bundling`, `vendoring`), and match a bare tool name only as the head noun phrase (standalone head, versioned name, or multi-word product-name compound), rejecting `CLI` qualifiers and single-word modifiers before a different head noun.
- Check whether the candidate tool matches the item's own repository in `src/devops_cli/roadmap/alternatives.py` (`_verdict_of`) before checking `reply.adr` and `inventory.uses`, returning `in-use` for the own repository while keeping genuine rejected-subject ADRs ahead of the inventory.
- Update the ADR census expectation for ADR 0005 (`github/codeql`) to `False` in `tests/roadmap/test_roadmap_adr.py`, add tests for the false-rejection replays (`#5524`, `#5323`, `#4719`) and ADR 0018 (`bubblewrap`), and update `docs/roadmap/alternatives.md` and `openspec/specs/roadmap-alternatives/spec.md`.

## Capabilities

### Modified Capabilities
- `roadmap-alternatives`: Refine ADR option rejection matching (`rejects()`) to ignore link targets, qualifiers, prepositional instruments, and packaging methods, and return `in-use` for the item's own repository before checking `adr` while keeping genuine ADR rejections ahead of inventory.

## Impact
- `src/devops_cli/roadmap/adr.py`
- `src/devops_cli/roadmap/alternatives.py`
- `docs/roadmap/alternatives.md`
- `tests/roadmap/test_roadmap_adr.py`
- `tests/roadmap/test_roadmap_alternatives_project_facts.py`

## Feasibility
Confirmed against `origin/main` (`4046839ec`):
- [`src/devops_cli/roadmap/adr.py:267`](src/devops_cli/roadmap/adr.py#L267) appends `child.attrGet("href")` to `marked` spans, and `rejects()` (`adr.py:326`) calls `names()` across the entire option text.
- [`src/devops_cli/roadmap/alternatives.py:1189`](src/devops_cli/roadmap/alternatives.py#L1189) confirms `reply.adr` before checking the item's repository and before `inventory.uses()`.
- Real ADRs (`docs/adr/0005`, `0006`, `0008`, `0014`, `0018`, `0021`, `0022`, `0024`) contain the exact phrases cited (`Vendoring Semgrep registry rules or bundling the CodeQL CLI`, ``Everything through the `gh` CLI``, `A Kubernetes Lease for each lock`, ``Kubernetes `metadata.generateName` ``, `[#2086](...)`, `The agent-sandbox controller`, `IBM Carbon tokens`, `GitHub Primer primitives`, `DBOS Transact in-process`, `APScheduler 4`).

## Existing Tool Considered
The alternatives check on #6441 returned `none` with no covering tool. Generic Markdown parsers tokenize inline spans (`markdown-it-py`, already used in `adr.py`) and ADR authoring CLIs manage files, but neither encodes option-subject matching or verdict precedence. Extending `adr.py` and `alternatives.py` avoids new dependencies and costs approximately 8k tokens to implement and test, ~2k tokens per maintenance edit, and under one day of engineering time. Fits in one pull request.
