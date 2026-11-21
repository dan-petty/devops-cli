# Design

## Decisions

- **Record the retirement in the `audit` row of `docs/SDLC.md` instead of adding a guard test.**: A test that reads `uv.lock` raises the count of the `test-tree` row, which only falls, and a deletion gets no test, so the document is the one place where the retirement stays visible.
- **Plan no bump of a Semgrep requirement file and no osv-scanner ignore entry.**: `probes` shows that the Semgrep requirement file and the ignore file are no files of the staged commit (#6555), and the only mcp pin left, `uv.lock` 2.3.0, is above the affected range.
- **Give both acceptance criteria to `pending-person`.**: The data that each criterion names is deleted, so no group can deliver it, and only a person decides that the item is obsolete.

## Rejected alternatives

- **Wait for a Semgrep release and compile the Semgrep requirement file again.**: `probes` says that the path of that file is no file of the staging commit, and commit ebec0158 deleted it with the tools lock (#6555), so no compile step and no pin is left to move.
- **Renew the osv-scanner ignore entry of GHSA-qx49-fqc8-xw99 in 3-day steps with new proof.**: `probes` says, word for word: The path `.osv-scanner-ignore.yaml` is no file of the staging commit, so no entry is left to renew.
- **Add an invariant test that asserts the mcp floor of `uv.lock`.**: `docs/TESTING.md:62:refuses a new test that reads a committed manifest or config file`, and the count of `tests/gate/tree_checks/config_reads.toml` only falls, so the test would fail the `test-tree` row.
- **File the bump in the devtools repository.**: `docs/SDLC.md:212:The devtools repository audits the locks of the tools that its image installs (#4363).` That repository owns the Semgrep pin and its Renovate updates, and it is outside this roadmap.
