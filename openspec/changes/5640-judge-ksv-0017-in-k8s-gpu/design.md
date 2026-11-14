# Design

## Decisions

- **Judge the alert with a dated ignore entry, not with a change of the DaemonSet.**: The container needs `privileged: true` for GPU device and sysfs access, #5646 owns the manifest change, and SECURITY.md allows the ignore entry when the change would break the workload.
- **Name #5646 as the tracking issue in the statement.**: It is open, it was split from this issue, and SECURITY.md requires a tracking issue in the entry.
- **Set the expiry to 3 days after the entry.**: SECURITY.md line 105 sets 3 days for an agent and at most 14 days in all, and a longer date is the owner's decision.
- **Assert the entry among the entries of the file, and not the only entry.**: #5371, #5641 and #5642 judge other alerts of the same DaemonSet, and #5371 adds the same entry, so the test accepts an additional entry with its own reason.
- **Guard the entry with a test that reads no clock.**: The test keeps the rule, the path, the statement and the expiry from drifting, and a test that reads today's date would fail unrelated pull requests after the expiry.
- **Keep the DaemonSet out of the diff.**: #5646 delivers the manifest change, and a second change of the same file here would conflict with it.
- **Leave `src/devops_cli/config/constants.py` and `src/devops_cli/security/trivy.py` unchanged.**: The scanner already names `.trivyignore.yaml` with `--ignorefile`, so the new entry needs no code.

## Rejected alternatives

- **Remove `privileged: true` from the DaemonSet in this pull request.**: #5646, split from this issue, states that GFD v0.16.2 needs this access and that a change which removes `privileged: true` now would break GPU feature discovery.
- **Dismiss the alert in code scanning.**: `SECURITY.md:106:A person dismisses the alert in code scanning, with a reason. An agent does not dismiss an alert.`
- **Add the entry to the plain `.trivyignore` file.**: `.trivyignore:7:Trivy has no path field in this file format, so the entry` — the entry would match the rule in every file instead of the one path.
- **Ask the owner for a longer expiry.**: SECURITY.md line 105 limits an agent to 3 days and 14 days in all, and this entry needs no longer date.

## Security

The plan keeps the privileged container of the GPU feature discovery DaemonSet, so the pod keeps host GPU device and sysfs access, and the ignore entry narrows that access to one rule and one path and adds no privilege. A person must confirm that the entry names the real tracking issue #5646 and that its expiry is no more than 3 days after the entry, because an agent must not extend the limit. The new test in `tests/security/test_trivy_config_ignore.py` fails if the entry loses its rule, its path, its tracking issue or its expiry date.
