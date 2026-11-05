# Design

## Decisions

- **The test scans the description of each option in the published schema of each read-only tool.**: It looks for `resolve`, `write`, `delete` and `create` in the base, `-s` and `-ing` forms. The issue names these verbs and names the help text as the signal. The generator copies the help text into the description of the published parameter. So the schema is what a model reads. The test names the tool and the option.
- **A past form of a verb does not match.**: `resolved` in `sandbox_network_policy.public_whitelist`, `sandbox_network_policy.local_whitelist` and `scan_injection.suppress` describes a result. `wrote` in `roadmap_refine.item` does the same. A match on them would need an exempt list. An exempt list hides the error that the test must show.
- **`pr check-readiness`, `roadmap refine`, `roadmap run` and `ci` are marked not read-only. Each command keeps its option.**: `--auto-resolve` and `--confirm` write to GitHub. `--fix` rewrites files, and it is on by default. The flag then says what the tool can do. No job role table names these tools, so no role loses a tool. The rule finds the first two. A person finds the other two by reading the options, so the table test names them.
- **`scan_injection` and `tf_plan` stay read-only. Their schemas drop `sarif` and `out`.**: Each command prints its result, so the model needs no file. SECURITY.md rule 11 says that a tool publishes no option for a path that the command writes, unless a path helper confines it. Nothing confines `sarif` or `out`. The dry-run class of `scan injection` is `no-external-request`, and the ratchet test requires a read-only tool for that class. The restriction follows the rule of `ai_ast_graph` and `scan_sbom`.
- **The verb pattern is a private constant of the test.**: Only the test reads it, so CONTRIBUTING.md section 5 puts it in that module.
- **The test builds a one-tool server for each case of the rule, with the signature that the generator makes.**: The rule then runs on the same kind of object that the repository check reads. No double replaces a tool.

## Out of scope

- **Tools that write local state.**: `ai_quiesce`, `ai_resume`, `ai_failover`, `ai_gateway_failover` and `review_export_feedback` write local state or a file. Dropping an option does not make them read-only, because the whole command writes. A flag that is not read-only fails the requirement `mcp-read-only-hint-agrees-with-no-external-request` and its ratchet test. Issue #3642 decides what the class means for the flag.
- **The words of `tf_notify_plan`.**: The command prints the comment and posts nothing, so the flag is right. Issue #3644 fixes the help text.
- **Paths with no confinement decision.**: `scan_injection.suppress` reads a path and `review_export_feedback.output` writes a path. Both stay as before. Issue #3480 gives each a decision.

## Rejected alternatives

- **Keep `tf_plan` not read-only and publish `out`.**: The first version did so. The tool then publishes a path that the command writes, and nothing confines it. SECURITY.md rule 11 and the requirement "Write path confinement" of `mcp-tool-path-confinement` forbid that.
- **Mark only `pr check-readiness` and add no general check.**: The scan finds more tools of the same kind. Acceptance criterion 1 of the issue says that no tool with a write option is read-only.
- **Remove `auto_resolve` from the published schema of `pr_check_readiness`.**: `_PATH_PARAM_RESTRICTIONS` takes an `allowed` list only. The entry must list the seven other options, and it drops each option that the command adds later. The option is also useful for a model that has the write right.
- **Scan option names, not descriptions.**: `--confirm`, `--out`, `--fix` and `--sarif` have names with no write verb. The check would miss four of the tools.
- **Widen the verbs to `post`, `execute`, `apply`, `restore` and `close`.**: These words find `roadmap_run.confirm` (`Execute`), `tf_notify_plan.pr_number` (`post`) and `ai_gateway_failover.reset` (`Restore`). The first is a write. The second is not, because the command posts nothing. The words also match text with no write: `sandbox_status.all_instances` (`Apply operation across all registered sandbox instances`), `ci.check` (`applying`), `gh_issues_list.state` (`closed`) and `pr_describe.issue` (`closes`). A word list cannot tell the groups apart. A person must read each flag. So the test keeps the four verbs of the issue, and the table holds the result of that reading.
- **Mark `scan_injection` not read-only.**: The dry-run ratchet test fails with that flag (see Feasibility in the proposal).
- **Mark the five local writers not read-only.**: The requirement `mcp-read-only-hint-agrees-with-no-external-request` and its ratchet test fail. A change to them needs a decision of its own, which issue #3642 holds.
- **Keep the old flag and rely on the description of the tool.**: A role server reads the flag and not the text, so the text does not stop a write.
