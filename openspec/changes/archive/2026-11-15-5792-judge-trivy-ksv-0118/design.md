# Design

## Decisions

- **Judge the alert with a dated ignore entry, not with a change of the DaemonSet.**: The container needs privileged access and the default pod security context for GPU discovery, #5646 owns the manifest change, and SECURITY.md allows the ignore entry when the change would break the workload.
- **Name #5646 as the tracking issue in the statement.**: It is open, it tracks the non-privileged GPU feature discovery manifest changes, and SECURITY.md requires a tracking issue in the entry.
- **Set the expiry to 3 days after the entry.**: SECURITY.md line 105 sets 3 days for an agent and at most 14 days in all, and a longer date is the owner's decision.
- **Assert the entry among the entries of the file, and not the only entry.**: Multiple rules are judged for the DaemonSet, so the test asserts the KSV-0118 entry specifically and accepts other entries.
- **Guard the entry with a test that reads no clock.**: The test keeps the rule, the path, the statement and the expiry from drifting, and a test that reads today's date would fail unrelated pull requests after the expiry.
- **Keep the DaemonSet out of the diff.**: #5646 delivers the manifest change, and an edit here would break GFD discovery.
- **Leave `src/devops_cli/config/constants.py` and `src/devops_cli/security/trivy.py` unchanged.**: The scanner already names `.trivyignore.yaml` with `--ignorefile`, so the new entry needs no code.

## Rejected alternatives

- **Set pod-level security context in the DaemonSet in this pull request.**: GFD v0.16.2 requires privileged execution to discover GPU devices and bus topology. Modifying pod securityContext now would break node GPU labeling.
- **Dismiss the alert in code scanning.**: `SECURITY.md:106:A person dismisses the alert in code scanning, with a reason. An agent does not dismiss an alert.`
- **Add the entry to the plain `.trivyignore` file.**: `.trivyignore` has no path field in this file format, so the entry would match the rule across all files instead of the single path.
- **Ask the owner for a longer expiry.**: SECURITY.md limits an agent to 3 days and 14 days in all, and this entry needs no longer date.

## Security

The plan keeps the default pod security context of the GPU feature discovery DaemonSet, and the ignore entry narrows that exception to rule KSV-0118 and path `k8s/gpu-feature-discovery/daemonset.yaml`. A person must confirm that the entry names the real tracking issue #5646 and that its expiry is no more than 3 days after the entry. The new test in `tests/security/test_trivy_config_ignore.py` fails if the entry loses its rule, its path, its tracking issue or its expiry date.
