# Task: Pytest Start-Up and Collection on the GitHub Runner Take Half of Today's 45 Seconds (#1735)

**Issue**: [#1735](https://github.com/dan-petty/devops-cli/issues/1735)
**Scope**: scope/ci
**Feasibility**: Measured on release/v0.2.38 at 79eaacb, on 2026-10-20.
- **The runner's test step:** in #1744's CI log, the step started at 17:28:16.9 and collection finished at 17:28:55.2, which is 38.3s.
  - Inside it, the gate's `uv run pytest` printed "Removed virtual environment at: .venv". It downloaded CPython 3.14.7 and every wheel and reinstalled 221 packages, while the workflow's `uv sync` had built the environment on 3.14.8.
  - The cause: the gate's child-environment allowlist (`DEFAULT_ALLOWED_ENV_PREFIXES` in `src/devops_cli/core/process.py`) dropped `UV_PYTHON`, `UV_CACHE_DIR` and `UV_PYTHON_INSTALL_DIR`.
- **Bytecode:** a four-worker collection here took 38.4s with no bytecode and 14.2s warm, and 28.9s with site-packages and `src` compiled, since pytest's rewritten test modules cannot be cached across fresh checkouts.
- **Narrowed runs:** a narrowed run of two trivial tests took 6.3-7.2s wall. cProfile showed pydantic-ai imported at every session start, in three places:
  - the support registration's import of `tests/support/fakes/model.py`, 2.9s;
  - the session fixture `guard_live_rag_data`, 4.9s with `qdrant_client`;
  - the per-test RAG reset's import of `devops_cli.ai.rag.investigator`, 2.4s.

## Description

- [x] The gate's children keep uv's own settings: `UV_` joins `DEFAULT_ALLOWED_ENV_PREFIXES`. A uv credential such as `UV_PUBLISH_TOKEN` still matches a denied pattern, which `test_a_child_uv_keeps_the_runners_uv_settings_but_not_its_credentials` checks.
- [x] The shared toolchain action's `uv sync` passes `--compile-bytecode`, so a fresh runner compiles the environment once, in parallel, rather than in every xdist worker. A workflow contract in `tests/test_ci.py` pins it.
- [x] `tests/support/bootstrap.py` registers as plugins only the support modules that could give pytest a fixture or hook:
  - one in which the test selector finds a fixture or hook;
  - one that imports pytest or another support module;
  - one that answers attribute lookups with a module-level `__getattr__` or `__dir__`.

  A plain helper such as the model fake loads when a test imports it. The four ways of hiding a fixture from the selector still fail the registration. `test_a_plain_helper_is_left_for_its_importers_to_load` covers the helper case, and the registration import-failure test now uses a module registration imports.
- [x] The session fixture `guard_live_rag_data` is removed. It refused only Qdrant URLs on the configured k8s domain, and the floor's network block already refuses every external lookup, every non-loopback connect and every loopback port the test process does not bind. With no configuration, as on CI, it refused nothing.
- [x] `reset_rag_state_per_test` resets only the RAG modules a test has loaded, since a module no test imported holds none of their state.
- [x] Measured on a quiet host:

  | Run | Before | After |
  |---|---|---|
  | Narrowed run of two trivial tests (`uv run pytest -n 0`) | 6.3-7.2s wall | 2.9-3.1s wall (0.6s in the session) |
  | `register_support_plugins` | 4.0s | 0.6s |
