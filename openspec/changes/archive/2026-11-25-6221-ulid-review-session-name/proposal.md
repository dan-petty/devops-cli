# Proposal: #6221

## Why
`devops review pr` and `devops review branch` build their `session_id` inline from `datetime.now(UTC).strftime("%Y%m%d-%H%M%S")` (`src/devops_cli/commands/review.py:661,918`), and `ReviewPipelineOrchestrator` falls back to the same format (`src/devops_cli/ai/review/pipeline.py:2128`). Two reviews started in the same second under one data directory collide on the same session name, causing the second review to fail at `ReviewSession.publish()` with `ReviewSessionExistsError`, exit 1, and skip posting its pull request comment (#6221).

## What Changes
- Add runtime dependency `python-ulid` with an exact pin in `pyproject.toml`, map `"python-ulid" = "ulid"` in `[tool.deptry] package_module_name_map`, and update `uv.lock`.
- Add `new_session_name()` and shared session start-time sort key `session_sort_key()` in `src/devops_cli/review/session.py`.
- Replace timestamp session naming in `devops review branch`, `devops review pr`, and `ReviewPipelineOrchestrator.__init__` with `new_session_name()` (leaving non-session sample validation directory naming unchanged).
- Sort published and in-flight sessions by decoded start time (ULID millisecond timestamp, legacy `YYYYMMDD-HHMMSS` UTC timestamp, then non-timestamp fallback) across `ReviewSessionStore._named_in` and `src/devops_cli/ui/data_providers.py`.
- Carries an OpenSpec delta for `review-session` because session naming, storage listing order, and command session IDs are observable behavior.

## Capabilities

### New Capabilities
- `review-session`: Unique Crockford base32 ULID session names generated per review and start-time ordering across ULID and legacy timestamp session folders.

### Modified Capabilities
- None.

## Impact
- `src/devops_cli/review/session.py`, `src/devops_cli/commands/review.py`, `src/devops_cli/ai/review/pipeline.py`, `src/devops_cli/ui/data_providers.py`, `pyproject.toml`, `uv.lock`.
- Adds one exact-pinned pure-Python runtime dependency (`python-ulid`).
- Fits in one pull request.

## Feasibility
Confirmed against `origin/main`:
- `src/devops_cli/commands/review.py:661` and `:918` compute `session_id = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")`.
- `src/devops_cli/ai/review/pipeline.py:2128` falls back to `datetime.now(UTC).strftime("%Y%m%d-%H%M%S")`.
- `src/devops_cli/review/session.py:247` and `src/devops_cli/ui/data_providers.py:435` sort session names in reverse lexicographic order, which puts legacy `2026...` folder names ahead of `01...` ULIDs unless decoded to timestamps.
- `python-ulid` is adopted on `#6221` after the owner reply and alternatives check.

## Existing Tool Considered
`python-ulid` (`https://pypi.org/project/python-ulid`) has verdict `covers` from the 2026-11-25 alternatives check on `#6221`. It generates 26-character Crockford base32 ULID strings ordered by millisecond start time and decodes timestamps via `ULID.from_str(name).datetime`. The change adopts `python-ulid` (pinned in `pyproject.toml` and mapped in `[tool.deptry]`), removes the inline `%Y%m%d-%H%M%S` session-id expressions at `commands/review.py:661,918` and `ai/review/pipeline.py:2128`, and keeps the existing staging, publish refusal, and legacy mixed-format sorting in `review/session.py`.
