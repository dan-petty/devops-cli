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
