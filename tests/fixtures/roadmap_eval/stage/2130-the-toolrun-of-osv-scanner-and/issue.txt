### Friction

Part of the tracker #772 (Part D: "The ruleset digest of osv-scanner and the Ruff config digest are settled here"; criterion 5: each ToolRun records its config and ruleset digests). The ToolRun of an osv-scanner run records no digest of its advisory database, and the ToolRun of a Ruff run records no digest of the Ruff configuration that it read. On 2026-10-24 the PyPI database of osv-scanner was 36 MB, above the file-size cap of the record's digest step, so the digest is not a plain file hash.

### What should happen

The ToolRun of osv-scanner records a digest that names the database it used (for example, the database's own modified time and the digest of its index, or a streamed hash of the files), and the ToolRun of Ruff records the digest of the configuration that Ruff resolved for the target.

### Evidence

- The #2096 delivery (2026-10-24): the 36 MB database and the file-size cap.
- #1983 put the ToolRun records in the SARIF run's property bag.

### Acceptance criteria

- [ ] The ToolRun of an osv-scanner run changes when its database changes, and stays the same when it does not.
- [ ] The ToolRun of a Ruff run changes when the Ruff configuration of the target changes.


Source: https://github.com/dan-petty/devops-cli/issues/772

<!-- devops-roadmap-refine:start -->
<!-- checked-at: sha=bb46660c8d12e28520a25e8171ec300c627df0db -->
## Proposed design

### Problem statement
The ToolRun record of an osv-scanner run does not capture a digest of the advisory database it used. The ToolRun record of a Ruff run does not capture a digest of the Ruff configuration it resolved. Without these digests, a user cannot verify which database version or configuration produced a given scan result. The osv-scanner PyPI database is 36 MB, above the file-size cap of the record's digest step, so a plain file hash is not possible.

### Acceptance criteria
- Criterion 1: The ToolRun of an osv-scanner run records a digest that changes when the database changes and stays the same when it does not.
  Verification: Run osv-scanner twice with the same database and confirm the ToolRun digest is identical. Update the database and run again, then confirm the digest differs.
- Criterion 2: The ToolRun of a Ruff run records a digest of the configuration that Ruff resolved for the target.
  Verification: Run Ruff twice with the same configuration and confirm the ToolRun digest is identical. Modify the Ruff configuration and run again, then confirm the digest differs.

### Key questions
- **What digest method should the osv-scanner ToolRun use for its database, given that the 36 MB PyPI database exceeds the file-size cap for a plain file hash?**: Use a streamed hash of the database files, or the database's modified time combined with a digest of its index. The exact method is a design choice for the implementer. (proposed)
- **What does 'the configuration that Ruff resolved for the target' mean for the digest?**: It is the final Ruff configuration after Ruff merges its defaults with the project's ruff.toml or pyproject.toml section. The digest covers the resolved configuration, not the raw file. (proposed)

### Fit
Fits in one pull request.

### Suspected block
None.

### Dependencies
None.
<!-- devops-roadmap-refine:end -->

<!-- devops-roadmap-record {"Effort": "Medium", "Owner": "Agent", "Priority": "P2-Medium", "Status": "Planned", "Value": "High", "refine.block_paths": null, "refine.blocked_by": null, "refine.body_hash": "043d41b863120f456b762c239492cca2961c4d577ba5c24df96ae33ce1585d43", "refine.failed_body_hash": null, "refine.needs_split": "false", "refine.next_step": "ready", "refine.section_hash": "62ee70bc066f7bb3bcf92514df2c7305083143c926982a87cc23cbac5753e282", "stage.branch": "feat/2130-the-toolrun-of-osv-scanner-and", "stage.file_cap": null, "stage.groups": "[[\"Add osv-scanner database digest to the ToolRun\", 3003], [\"Add Ruff configuration digest to the ToolRun\", 2982]]", "stage.needs_split": null, "stage.pr": "2978", "stage.ready": "2978", "stage.sha": "fb4b34c38cfb9e44f02e0c83fe6a425d6374d3eb"} -->
