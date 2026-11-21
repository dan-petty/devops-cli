# Proposal

## Why

Issue #6480 asks for two things: a Semgrep tools lock that takes mcp 1.30.0 or later, and the removal of the five mcp 1.29.0 ignore entries of the osv-scanner audit. Both targets left the tree with #6555, and the only mcp pin left, uv.lock 2.3.0, is above the affected range of the advisory, so the item can no longer be built as written. The change records where the pin and its advisories are owned now, and it plans no code that pretends the retired files are still here.

## What Changes

- Extend the `audit` row of `docs/SDLC.md` with the consequence of the devtools ownership: the Semgrep requirement file and the advisories of the tools that the image installs belong to the devtools repository, which audits and bumps them.
- State in the same row that this repository therefore holds no Semgrep requirement file and no osv-scanner ignore entry, so GHSA-qx49-fqc8-xw99 needs no entry here.
- Plan no bump and no ignore entry: `probes` shows that both files are no files of the staged commit, and the only mcp pin, `uv.lock` 2.3.0, is above the affected range.
- No spec delta: the only changed path is under `docs/`, and a document changes no behavior that a consumer observes.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Documents: `docs/SDLC.md`

## Feasibility

- The issue cannot be built as written. `probes` says, word for word: The path `src/devops_cli/tools_lock/semgrep.txt` is no file of the staging commit. Commit ebec0158 2026-11-20 refactor(deps): delete install-tools and the tools lock (#6555) deleted or renamed it.
- `probes` says, word for word: The path `.osv-scanner-ignore.yaml` is no file of the staging commit.
- `list_files` of the repository root listed `.npm-audit-ignore.yaml` and no `.osv-scanner-ignore.yaml`, and `search_code` for `semgrep.txt`, `osv-scanner-ignore`, `mcp==` and `1.29.0` returned no hit outside `CHANGELOG.md` and `openspec/changes/archive/`, so 0 files of the staged tree pin mcp 1.29.0 or read a retired ignore file.
- `read_file` of `uv.lock` showed `uv.lock:2598:name = "mcp"` and `uv.lock:2599:version = "2.3.0"`, above the 2.2.0 that closes the affected range of GHSA-qx49-fqc8-xw99 on the 2.x line.
- `read_file` of `CHANGELOG.md` showed `CHANGELOG.md:23:* **deps:** delete install-tools and the tools lock`, so the retirement shipped in release 0.185.2.
- `read_file` of `docs/SDLC.md` showed `docs/SDLC.md:212:The devtools repository audits the locks of the tools that its image installs (#4363).`, so the row gives the ownership of the locks and not what that ownership means for an advisory of one of their tools.
- `references` for `semgrep.txt` listed 14 files and `references` for `osv-scanner-ignore` listed 8 files, and every one of them sits under `openspec/changes/archive/`, so 0 files outside the archive name either retired path.
- `read_spec` of `ci-dependency-audit` gave the purpose and the four requirements, and they name only `uv audit`, the root `package-lock.json` and `.npm-audit-ignore.yaml`, so the living spec holds no osv-scanner ignore rule and the change needs no delta.
- `read_file` of `tests/invariants/test_declared_dependencies.py` showed one test that reads `pyproject.toml` and `uv.lock`, and `search_code` for that module returned no hit in `tests/gate/tree_checks/config_reads.toml`, so a new config-reading test would raise a count that only falls.
- The `other` finding is fixed at its place: the group adds no test and reads no lock, so `docs/TESTING.md:62:refuses a new test that reads a committed manifest or config file` stays satisfied and the `test-tree` row keeps its counts.
- The `contrived_test` finding is fixed at its place: the group adds no test, because a deletion gets no test and a group that changes only a document is `other`.
- The `criterion_dropped` finding is no defect of the plan: the criterion names the Semgrep requirement file and its mcp 1.29.0 entries, and `probes` says, word for word, The path `src/devops_cli/tools_lock/semgrep.txt` is no file of the staging commit, so no group can compile that file, and the rule that a change plans no code for a false premise forbids a group that pretends to. Both criteria go to `pending-person`.
- The first check against the real system is `uv run devops ci --check --only audit`: it exits 0 and its output holds no GHSA-qx49-fqc8-xw99 row. Its precondition is a checkout of the repository and a network to the PyPI and npm registries, because it runs `uv audit` and `npm audit`.
- The verify `uv run devops ci --check --only docs` runs `devops docs check` over the tree, so its precondition is a checkout of the repository, and it needs no client, no cluster and no network.
- The plan introduces no program and no new exit code, so it adds no failure class: `uv`, `python`, `devops` and `npm` are runner tools, and `docs` and `audit` are rows of `devops ci`. The pod keeps `readOnlyRootFilesystem: true`, `runAsNonRoot: true`, `capabilities.drop: ALL`, `allowPrivilegeEscalation: false` and `seccompProfile: RuntimeDefault`, and `devops docs check` writes no file.

## Existing Tool Considered

renovatebot/renovate (AGPL-3.0, maintained, last activity 2026-11-19) is in use and already opens the bump of a pin, so the change adopts it, builds no code and deletes no internal code.

## Dependencies

None.
