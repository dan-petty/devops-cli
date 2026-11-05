# Design

## Decisions

- **The test scans the description of each option in the published schema of each read-only tool, for `resolve`, `write`, `delete` and `create` in the base, `-s` and `-ing` forms.**: The issue names these verbs and names the help text as the signal. The generator copies the help text into the description of the published parameter, so the schema is what a model reads. The test names the tool and the option.
- **A past form of a verb does not match.**: `resolved` in `sandbox_network_policy.public_whitelist`, `sandbox_network_policy.local_whitelist` and `scan_injection.suppress`, and `wrote` in `roadmap_refine.item`, describe a result and write nothing. A match on them would need an exempt list, and an exempt list hides the error that the test must show.
- **`pr check-readiness`, `roadmap refine` and `tf plan` are marked not read-only, and each command keeps its option.**: `--auto-resolve` and `--confirm` write to GitHub. `--out` writes the plan file that `tf_apply` takes as `plan_file`, so the option has a use for a model. The flag then says what the tool can do. No job role table names these tools, so no role loses a tool.
- **`scan_injection` stays read-only and its schema drops `sarif`.**: The command prints its findings, and a SARIF file is for a CI upload that a person starts. The dry-run class of the command is `no-external-request`, and `test_mcp_exposure_table_no_external_request_read_only` fails when the tool is not read-only. The restriction follows the rule of `ai_ast_graph` and `scan_sbom`, which leave out a file option that the model does not need.
- **The verb pattern is a private constant of the test.**: Only the test reads it, so CONTRIBUTING.md section 5 puts it in that module.
- **The test builds a one-tool server for each case of the rule, with the signature that the generator makes.**: The rule then runs on the same kind of object that the repository check reads, and no double replaces a tool.

## Rejected alternatives

- **Mark only `pr check-readiness` and add no general check.**: The scan finds three more tools of the same kind. Acceptance criterion 1 of the issue says that no tool with a write option is read-only.
- **Remove `auto_resolve` from the published schema of `pr_check_readiness`.**: `_PATH_PARAM_RESTRICTIONS` takes an `allowed` list only. The entry must list the seven other options, and it drops each option that the command adds later. The option is also useful for a model that has the write right.
- **Scan option names, not descriptions.**: `--confirm`, `--out` and `--sarif` have names with no write verb, and the check would miss three of the four tools.
- **Widen the verbs to `post`, `execute`, `apply`, `restore` and `close`.**: These words find `roadmap_run.confirm` (`Execute`), `tf_notify_plan.pr_number` (`post`) and `ai_gateway_failover.reset` (`Restore`). They also match words with no write: `sandbox_status.all_instances` (`Apply operation across all registered sandbox instances`), `ci.check` (`applying`), `gh_issues_list.state` (`closed`) and `pr_describe.issue` (`closes`). A word list cannot tell the two groups apart. A person must read each flag. The issue names four verbs, so this change keeps them.
- **Mark `scan_injection` not read-only.**: The dry-run ratchet test fails with that flag (see Feasibility in the proposal).
- **Keep the old flag and rely on the description of the tool.**: A role server reads the flag and not the text, so the text does not stop a write.
