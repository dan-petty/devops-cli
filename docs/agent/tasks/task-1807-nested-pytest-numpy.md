# Task: A Nested In-Process Pytest Run No Longer Evicts numpy for the Tests After It (#1807)

**Issue**: [#1807](https://github.com/dan-petty/devops-cli/issues/1807)
**Scope**: scope/ci
**Feasibility**: Run serially in one process, `pytest -n 0 tests/test_ai_test_gen.py tests/test_ai_subcommands_rag.py::test_try_retrieve_rag_context_success` failed at the base every time, and the RAG test passed alone and after `tests/test_ci_repeat.py`, `tests/invariants/test_hermetic_floor.py` and `tests/test_isolation_tripwire.py`. Logging the exception that `_try_retrieve_rag_context` swallows showed `ImportError: cannot load module more than once per process`, raised from `numpy/_core/multiarray.py` while `qdrant.py` imported `qdrant_client.http.models`. `Pytester.inline_run` restores `sys.modules` to the snapshot taken before the run. The nested session of `test_ai_test_gen.py` passes `-o addopts=`, which drops the repository's `-p no:randomly`, so it loaded `pytest-randomly`, which imports numpy. The restore removed numpy from `sys.modules`, its C extension stayed loaded, and the next import of numpy in that worker failed.

## Description

- [x] The nested run in `tests/test_ai_test_gen.py` passes `-p no:randomly`, as the repository's `addopts` does for every session, so it imports no numpy.
- [x] The test asserts that the nested run left numpy as it found it: a conftest in the nested session records whether numpy is in `sys.modules` when the session finishes, and the test compares that with the state before the run. The assertion does not import numpy itself, because a numpy first imported inside a test that holds the `pytester` fixture is removed from `sys.modules` when the fixture is torn down, which is the failure it guards against. It fails at the base.
