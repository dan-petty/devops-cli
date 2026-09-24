# Task 421: Tests That Cannot Fail Correctly

**Issue**: [#421](https://github.com/dan-petty/devops-cli/issues/421)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/cli`, `priority/p1-high`

---

## 1. Description & Objectives

Eight tests assert `pytest.raises(Exception)` and nine pass an unescaped regex to `match=`. `tests/test_ai_cmd.py:264` passes if *any* exception is raised, including a `TypeError` introduced by an unrelated refactor — the test certifies without checking, and would keep passing through the very regression it exists to catch. `tests/test_argo_crd.py:213` matches `"missing 'metadata.name'"` where `.` is a wildcard, so the assertion is weaker than it reads.

#### Key Deliverables:
- Context & Rationale*: Eight tests assert `pytest.raises(Exception)` and nine pass an unescaped regex to `match=`. `tests/test_ai_cmd.py:264` passes if *any* exception is raised, including a `TypeError` introduced by an unrelated refactor — the test certifies without checking, and would keep passing through the very regression it exists to catch. `tests/test_argo_crd.py:213` matches `"missing 'metadata.name'"` where `.` is a wildcard, so the assertion is weaker than it reads.
- Deliverable*: Narrow every blind `pytest.raises` to the specific exception type the code contracts to raise, and make `match=` patterns raw or `re.escape`d. Enforce with `B017` and `RUF043` so the class cannot return.
- Constraint*: A test narrowed to the wrong exception type is worse than a blind one, because it fails for a reason unrelated to the behaviour under test. Each narrowing needs the contract checked, not guessed from the current implementation.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
