# Design

## Decisions

- **Store helm commands as a list of argument lists (`list[list[str]]`) under the key `helm_commands`.**: This matches the format that `runtime._run_cmd` receives and that `_build_helm_upgrade_cmd` returns. A test can compare exact arguments without parsing a joined string.
- **Keep the existing `helm_releases` key alongside the new `helm_commands` key.**: Existing consumers and tests that read `helm_releases` do not break. The new key adds the detail the issue asks for.
- **Include `helm repo update` in the command list.**: The real run calls `helm repo update` after all `helm repo add` calls. The dry-run rule says the dry run returns the requests the real run would make.
- **Pass `is_v4=False` to `_build_helm_upgrade_cmd` in the dry-run branch.**: The dry run does not query the cluster for the Helm version. The same builder function is used; the `is_v4` input differs because the dry run has no cluster to ask. The output still carries chart, version, namespace, and values.
- **Extract `_build_helm_repo_cmds` so both paths build repo commands from the same code.**: The requirement says the commands are built by the same argument builders the real run uses. A shared builder guarantees a change to the builder changes both the dry-run output and the real run.

## Rejected alternatives

- **Store helm commands as joined command strings.**: A test must re-split to check individual flags. The argument-list format preserves boundaries and matches the return type of `_build_helm_upgrade_cmd`.
- **Replace `helm_releases` with `helm_commands`.**: 13 test files and external scripts read `helm_releases`. Replacing it breaks every consumer in the same PR. Keeping both is backward compatible.
- **Omit `helm repo update` from the command list.**: The real run makes this request. The dry-run rule (#412) requires the dry run to return every request the real run would make.
- **Use structured objects with type and fields for each command.**: The command list already carries all fields. A schema to maintain adds cost without adding information a test needs.
