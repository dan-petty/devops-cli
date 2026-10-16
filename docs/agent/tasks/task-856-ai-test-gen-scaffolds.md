# Task: Emit Failing Scaffolds in `devops ai test-gen` (#856)

**Issue**: [#856](https://github.com/dan-petty/devops-cli/issues/856)
**Status**: Done
**Feasibility**: Verified against `src/devops_cli/ai/test_gen.py`, `src/devops_cli/commands/ai.py:2013-2060`, and `src/devops_cli/ai/mcp/server.py:1307-1314`; confirmed `synthesize_unit_tests` previously emitted presence-only `assert hasattr(...)` and `assert ... is not None` assertions while reporting `Synthesized N unit test(s)`.

## Summary

- Updated `src/devops_cli/ai/test_gen.py` so every generated test function ends with `pytest.fail("expected behaviour of <function> not written")` without emitting presence-only assertions (`hasattr` / `is not None`), and resolved valid Python dotted import paths for files outside `src/`.
- Updated `devops ai test-gen` (`src/devops_cli/commands/ai.py`), `ai_test_gen` (`src/devops_cli/ai/mcp/server.py`), and `HELP.ai` (`src/devops_cli/lang/en/help.py`) to describe the output as unit test scaffolds rather than synthesized unit tests, and regenerated reference documentation (`docs/CLI_REFERENCE.md`, `docs/MCP_TOOLS.md`, `docs/commands/ai.md`).

## Acceptance Criteria

- [x] The generated code parses (`tests/test_ai_test_gen.py::test_test_gen_emits_failing_scaffolds_without_presence_assertions`).
- [x] Every test function contains `pytest.fail` and no presence assertion (`tests/test_ai_test_gen.py::test_test_gen_emits_failing_scaffolds_without_presence_assertions`).
- [x] A `pytester` run reports every generated test as failed (`tests/test_ai_test_gen.py::test_test_gen_emits_failing_scaffolds_without_presence_assertions`).
- [x] No output says `'Synthesized'` (`tests/test_ai_test_gen.py::test_test_gen_emits_failing_scaffolds_without_presence_assertions`).
- [x] `devops docs check` passes, and the new tests take at most `1 s`.
