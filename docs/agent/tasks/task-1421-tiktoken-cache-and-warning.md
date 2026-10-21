# Task #1421 — Populate Tiktoken Cache at Image Build and Warn on Heuristic Fallback

**Issue**: [#1421](https://github.com/dan-petty/devops-cli/issues/1421)
**Feasibility**: Confirmed against `src/devops_cli/ai/context_budget.py` (`_get_tiktoken_encoding`), `tiktoken.load.read_file_cached`, `Dockerfile`, `.devcontainer/Dockerfile`, and `k8s/devops/cronjob.yaml`. Neither `Dockerfile` nor `.devcontainer/Dockerfile` pre-populated `TIKTOKEN_CACHE_DIR`, and `k8s/devops/cronjob.yaml` runs with `readOnlyRootFilesystem: true` and `emptyDir` mounts on `/tmp` and `/home/devops`, so `_get_tiktoken_encoding` attempted to download BPE files over HTTPS on first use and logged failures only at `DEBUG` before caching `None` for the life of the process.

## Summary

Pre-populated `TIKTOKEN_CACHE_DIR` (`cl100k_base` and `o200k_base`) during image builds in `Dockerfile` (`/app/.cache/tiktoken`) and `.devcontainer/Dockerfile` (`/usr/local/share/tiktoken`), resolved local tiktoken cache directories in `devops_cli.ai.context_budget` without attempting network downloads when a cache directory is missing or empty, and logged one `WARNING` naming the cache directory when falling back to the 4-characters-per-token heuristic.

## Deliverables

- [x] Pre-populate `cl100k_base` and `o200k_base` into `/app/.cache/tiktoken` in `Dockerfile` (`builder` stage), copy `/app/.cache/tiktoken` into the `service` stage, and set `ENV TIKTOKEN_CACHE_DIR=/app/.cache/tiktoken`.
- [x] Pre-populate `cl100k_base` and `o200k_base` into `/usr/local/share/tiktoken` in `.devcontainer/Dockerfile` and set `ENV TIKTOKEN_CACHE_DIR=/usr/local/share/tiktoken`.
- [x] Update `_get_tiktoken_encoding` in `src/devops_cli/ai/context_budget.py` to resolve the local tiktoken cache directory, fail fast when the cache directory is missing or empty rather than attempting an outbound HTTP download, and log one `WARNING` naming the cache directory on fallback.
- [x] Add offline unit tests in `tests/test_context_budget.py` verifying encoding load from a prepared `TIKTOKEN_CACHE_DIR` with sockets blocked, single `WARNING` log naming the cache directory on failed load, and `Dockerfile` / `.devcontainer/Dockerfile` cache population.
- [x] Add changelog fragment `changelog.d/1421.md`.

## Verification

- [x] Verified `uv run devops ci test tests/test_context_budget.py tests/test_agent_task_files.py` passes with each test call phase well under 1 s.
- [x] Verified `uv run devops ci` passes all quality gates.
