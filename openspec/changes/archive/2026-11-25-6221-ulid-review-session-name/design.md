# Design

## Decisions
- Add `new_session_name() -> str` in `src/devops_cli/review/session.py` returning `str(ULID())` from `python-ulid`, and update `ReviewSession.name` and `ReviewSessionStore.sessions` docstrings from timestamp wording to ULID session ID wording (`src/devops_cli/review/session.py:83,219`).
- Call `new_session_name()` in `src/devops_cli/commands/review.py:661` (`branch`), `src/devops_cli/commands/review.py:918` (`pr`), and `src/devops_cli/ai/review/pipeline.py:2128` (`ReviewPipelineOrchestrator.__init__`), while leaving sample-validation `run_dir` timestamp naming (`src/devops_cli/commands/review.py:2509`) unchanged.
- Add `session_sort_key(name: str) -> tuple[int, datetime, str]` in `src/devops_cli/review/session.py` that returns `(1, ULID.from_str(name).datetime, name)` for ULID names, `(1, datetime.strptime(name, "%Y%m%d-%H%M%S").replace(tzinfo=UTC), name)` for legacy timestamp names, and `(0, datetime.min.replace(tzinfo=UTC), name)` for any other directory name. Use `session_sort_key` with `reverse=True` in both `ReviewSessionStore._named_in` (`src/devops_cli/review/session.py:247`) and `_listed_sessions` (`src/devops_cli/ui/data_providers.py:435`) so `sessions()`, `in_flight()`, `latest()`, and the dashboard agree on newest-first ordering.
- Add an exact-pinned `"python-ulid==..."` dependency in `pyproject.toml`, map `"python-ulid" = "ulid"` under `[tool.deptry] package_module_name_map` (`pyproject.toml:443`), and update `uv.lock`.

## Rejected alternatives
- Keep `%Y%m%d-%H%M%S` with an inline counter or random suffix: rejected under `AGENTS.md` Rule 3 because `python-ulid` covers unique, sortable millisecond IDs without bespoke collision logic at `src/devops_cli/commands/review.py:661,918`.
- Use standard-library `uuid.uuid7()`: rejected because it yields 36-character hyphenated strings without a ULID timestamp decoder (`ULID.from_str(name).datetime`), whereas `#6221` adopts `python-ulid`.
- Keep raw reverse lexicographic sort on directory names: rejected because legacy `2026...` directories always sort ahead of `01...` ULID directories, breaking `ReviewSessionStore.latest()` (`src/devops_cli/ai/review/runner.py:119`) and `_listed_sessions()` (`src/devops_cli/ui/data_providers.py:435`).
- Rename published legacy session folders on disk: rejected because session folder names are durable external references used by `devops review verify` (`tests/commands/test_review.py:53`).
