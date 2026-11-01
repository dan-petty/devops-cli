### Problem Description

`devops config unset <key>` stops with a `TypeError` traceback when the config file gives the key through a YAML merge key (`<<: *anchor`). `_find` in `src/devops_cli/config/round_trip.py` finds the key in the merged mapping, because ruamel.yaml lists merged keys as keys of the mapping. It then asks for the line of the key with `node.lc.key(dotted)`, and ruamel.yaml gives no position for a merged key.

`devops config audit-keys` loads the file with PyYAML, which resolves the merge, so it reports the key as a plaintext secret. Thus the audit reports a leak that `devops config unset` cannot remove, and the audit keeps failing. The key of the anchor mapping, such as `a.b.api_key` below, is the real place of the value, and the audit does not scan it because it is three levels deep.

### Reproduction Steps

1. Make a temporary `HOME` and a git repository in a temporary directory.
2. Write this text to `config.yaml` in the repository:
   ```yaml
   a:
     b: &d
       api_key: FAKE-2513-value
   ai:
     <<: *d
   ```
3. Set `PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring`. Run `devops config audit-keys` in the repository. The audit reports `<repo>/config.yaml:ai.api_key`.
4. Run `devops config unset ai.api_key` in the repository.

### Expected vs Actual Behavior

Expected: the command exits 1 with a message that names the file and says that the key comes from a merge key. Or it removes the value from the mapping that holds it. It prints no traceback.

Actual: step 4 prints a traceback that ends with `TypeError: 'NoneType' object is not subscriptable` at `round_trip.py:161`.

### Environment Diagnostics

devops-cli 0.16.1 at origin/main, ruamel.yaml and PyYAML as locked in `uv.lock`, Python 3.14.10, Linux.

### Logs, Traces, or Terminal Output

```text
Security Alert: Found plaintext secrets stored in config files: ['<repo>/config.yaml:ai.api_key']. ...
$ devops config unset ai.api_key
  ...
  161 |   return (*prefix, dotted), int(node.lc.key(dotted)[0]) + 1
TypeError: 'NoneType' object is not subscriptable
```

### Pre-Submission Checklist

- [x] I have verified that no sensitive credentials, private keys, or internal tokens are contained in this issue report.
- [x] I have checked existing issues and pull requests to ensure this is not a duplicate.


Source: https://github.com/dan-petty/devops-cli/issues/2513

<!-- devops-roadmap-refine:start -->
<!-- checked-at: sha=19a2e084e57bbf2c806fb9e7fdfd5905471f79d1 -->
## Proposed design

### Problem statement
devops config unset crashes with a TypeError when the target key is present only through a YAML merge key (<<: *anchor). The _find function in round_trip.py calls node.lc.key(dotted), which returns None for merged keys, and the code then indexes into None. The user sees a traceback instead of a clear message, and the audit keeps reporting a secret that the command cannot remove.

### Acceptance criteria

### Requirement: Merge key unset reports a clear error
When the target key is present only through a YAML merge key, devops config unset SHALL exit with code 1 and print a message that names the file and states the key comes from a merge key.

#### Scenario: unset a merge-derived key
- **WHEN** the config file defines the key via <<: *anchor and the user runs devops config unset on that key
- **THEN** the command exits 1, prints a message naming the file and mentioning the merge key, and prints no Python traceback

### Requirement: Direct key removal is unchanged
When the target key is directly present in the file, devops config unset SHALL remove the key and exit with code 0.

#### Scenario: unset a directly-present key
- **WHEN** the config file holds the key as a direct entry and the user runs devops config unset on that key
- **THEN** the key is removed from the file and the command exits 0

### Existing Tool Considered
The project already uses ruamel.yaml for round-trip YAML editing. ruamel.yaml lists merged keys as keys of the mapping but gives no position for them, so node.lc.key() returns None. No external tool covers the need to detect a merge-derived key and report a friendly error. The fix is a few lines in the project's own round_trip.py: check whether node.lc.key(dotted) is None before indexing, and raise a ConfigurationError. Written cost: roughly 10 tokens of new code, no new dependency, no ongoing maintenance beyond the existing module.

### Key questions
- **Why does node.lc.key(dotted) return None for a merge-derived key?**: ruamel.yaml resolves merge keys into the mapping so that dotted in node is True, but the merged key has no position in the source text. The lc (line/column) table holds no entry for it, so lc.key(dotted) returns None. Indexing None[0] raises TypeError. [sources: src/devops_cli/config/round_trip.py:161]
- **Should the fix raise a clear error or remove the value from the anchor mapping?**: Raise a ConfigurationError. The anchor may be shared by multiple merge targets, so removing from the anchor would silently affect keys the user did not ask to remove. A clear error names the file and tells the user to remove the key from the anchor mapping directly. (best practice) [sources: src/devops_cli/config/round_trip.py]
  - Chosen: Raise ConfigurationError naming the file and the merge key. Safe: does not modify a shared anchor. Clear: tells the user exactly where to act. Matches the existing error pattern in the module.
  - Rejected: Remove the value from the anchor mapping. Rejected: the anchor may be shared by other merge targets. Removing from it would silently change keys the user did not request, and the user asked to remove ai.api_key, not a.b.api_key.
- **What should the error message say?**: The message SHALL name the file and state that the key comes from a YAML merge key. This follows the existing ConfigurationError pattern in the module, for example 'Cannot save the settings: {name} is not valid YAML'. (best practice) [sources: src/devops_cli/config/round_trip.py]
  - Chosen: Name the file and state the key comes from a merge key. Matches the existing error style in the module. Gives the user enough to locate and fix the key in the anchor.
  - Rejected: Print a generic 'key not found' message. Rejected: the key is found in the merged mapping. A 'not found' message is misleading and does not tell the user what to do.

### Fit
Fits in one pull request.

### Suspected block
None.

### Dependencies
None.
<!-- devops-roadmap-refine:end -->

<!-- devops-roadmap-record {"Effort": "Low", "Priority": "P1-High", "Status": "In Review", "Value": "High", "implement.branch": "fix/2656-devops-config-unset-stops-with-a", "implement.job": "devops-cli-runner-20261030-202214-d182", "implement.job_state": "failed", "implement.pr": "2719", "implement.spend": "{\"requests\": 9, \"input_tokens\": 105240, \"output_tokens\": 562}", "implement.stopped": "job", "refine.block_paths": null, "refine.blocked_by": null, "refine.body_hash": "7db34093768c65603bafa52c2abe4ec479442941dc170acd4d0c49d9cdd39127", "refine.failed_body_hash": null, "refine.needs_split": "false", "refine.next_step": "ready", "refine.section_hash": "f5d994f82ad3a41d240601716fb5d28bb57ae802df56df5c4749a2b4627d7f45", "stage.branch": null, "stage.groups": null, "stage.needs_split": null, "stage.pr": null, "stage.sha": null} -->
