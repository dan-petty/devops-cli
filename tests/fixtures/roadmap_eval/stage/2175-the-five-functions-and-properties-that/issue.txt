### What happened

Five functions and properties in `src/` have no caller, and #1910 does not list them. `git grep -n -w <name> origin/main -- src tests docs '*.md' '*.yaml' '*.toml'` at b170358e finds only the definition. None of them carries a decorator that registers it, and none overrides a method of a library class.

| Definition | Name |
| :--- | :--- |
| `src/devops_cli/ai/client/streaming.py:164` | `StreamingTokenProcessor.thinking_detected` (property) |
| `src/devops_cli/ai/client/unified.py:215` | `LLMClient._get_ollama_semaphore` (classmethod) |
| `src/devops_cli/ai/thinking_stream.py:339` | `ThinkingStreamProcessor.unique_thinking` (property) |
| `src/devops_cli/config/settings.py:219` | `_validation_error_key` |
| `src/devops_cli/grafana/schema.py:145` | `Dashboard.grid_width` (property) |

### What should happen

The five definitions are deleted, with any import or constant that only they use.

### Evidence

- The coverage audit of 2026-10-24 listed 43 candidates (`dead-code-candidates.json`, at f4d7066b). Each was checked again at b170358e for callers, decorators and base classes. 19 were live (framework hooks, `@mcp.resource` functions, names used as strings). 17 of the rest are in #1910, and #1910 lists `set_mcp_sampling_model` and `to_cli` for the same check. These five are the rest.

### Acceptance criteria

- [ ] The five definitions are deleted.
- [ ] `git grep -n -w <name>` prints nothing in `src/`, `tests/` and `docs/` for each name.
- [ ] A test that only calls a deleted name goes with it, and the pull request names it.
- [ ] `uv run devops ci` passes, and the coverage stays at or above `fail_under`.

Related: #1910 deletes the other 17 names.


Source: https://github.com/dan-petty/devops-cli/issues/1910

<!-- devops-roadmap-refine:start -->
<!-- checked-at: sha=bb46660c8d12e28520a25e8171ec300c627df0db -->
## Proposed design

### Problem statement
Five functions and properties in src/ have no caller, no registering decorator, and no library override. Issue #1910 lists 17 other dead-code names for the same check. These five are the remainder and should be deleted to remove dead code from the tree.

### Acceptance criteria
- Criterion 1: All five definitions are deleted from their files.
  Verification: Open each of the five files and confirm the named definition is absent.
- Criterion 2: No reference to any of the five names remains in src/, tests/, or docs/.
  Verification: Run `git grep -n -w ` for each of the five names. Confirm the output is empty across src/, tests/, and docs/.
- Criterion 3: Any test that exclusively calls a deleted name is removed, and the pull request description names it.
  Verification: Read the pull request description. Confirm it lists every removed test by name. Confirm the test file no longer contains the removed test.
- Criterion 4: The CI gate passes and coverage stays at or above the fail_under value.
  Verification: Run `uv run devops ci`. Confirm the exit code is 0 and the reported coverage is at or above the `fail_under` value in `pyproject.toml`.

### Key questions
- **Are any of the five names called, registered by a decorator, or overriding a library method?**: No. A git grep at commit b170358e finds only the definition line for each name. None carries a decorator, and none overrides a base-class method. [sources: src/devops_cli/ai/client/streaming.py:164, src/devops_cli/ai/client/unified.py:215, src/devops_cli/ai/thinking_stream.py:339, src/devops_cli/config/settings.py:219, src/devops_cli/grafana/schema.py:145]
- **Is issue #1910 a prerequisite for this work?**: No. Issue #1910 deletes 17 other dead-code names. This issue deletes the remaining five. They are independent and can be delivered in any order. (proposed)
- **Do any of the five definitions have exclusive imports or constants that must also be removed?**: This must be confirmed during implementation. If a deleted name is the sole user of an import or constant, that import or constant is removed in the same pull request. (proposed)

### Fit
Fits in one pull request.

### Suspected block
None.

### Dependencies
None.
<!-- devops-roadmap-refine:end -->

<!-- devops-roadmap-record {"Effort": "Low", "Owner": null, "Priority": "P2-Medium", "Status": "Planned", "Value": "Low", "implement.branch": "refactor/2175-the-five-functions-and-properties-that", "implement.group": "1", "implement.job": "devops-cli-runner-20261101-102809-c4b3", "implement.job_digest": "sha256:59fd1dd8fc8586f5c4fc86d4fe6818fa0a6706468788fcfc6508544092eb788e", "implement.job_state": "succeeded", "implement.pr": "3000", "implement.sha": "ada8277296d6b579384d37b021c329256012ef66", "implement.spend": "{\"requests\": 89, \"input_tokens\": 2456216, \"output_tokens\": 9585}", "implement.stopped": null, "refine.block_paths": null, "refine.blocked_by": null, "refine.body_hash": "3905aee2a87db031abc4b3952295aaf2d3386ac774d2b95ca683623b1ad00529", "refine.failed_body_hash": null, "refine.needs_split": "false", "refine.next_step": "ready", "refine.section_hash": "c5f788f2af750c93322cf8f1d4fdced5f7cc9afe84e0e8546ff3524e4f399978", "stage.branch": "refactor/2175-the-five-functions-and-properties-that", "stage.file_cap": null, "stage.groups": "[[\"Delete thinking_detected from streaming.py\", 2906], [\"Delete _get_ollama_semaphore from unified.py\", 2930], [\"Delete unique_thinking from thinking_stream.py\", 2906], [\"Delete _validation_error_key from settings.py\", 2907], [\"Delete grid_width from schema.py and run CI\", 2877]]", "stage.needs_split": null, "stage.pr": "2983", "stage.ready": "2983", "stage.sha": "ec90a4da5c5fa9792b9ae4e51807923ec432a26f"} -->
