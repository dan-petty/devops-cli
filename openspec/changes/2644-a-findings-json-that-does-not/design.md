# Design

## Decisions

- **Create a single shared loader function in review/session.py.**: One place to format the error, one place to test, and the issue identifies the missing loader as the root cause.
- **Raise the project's ValidationError from devops_cli.exceptions.validation rather than a new exception type.**: The exit seam of `new_typer()` (`OTelTyper`) already prints a `DevOpsCLIError` as one error line and exits with its `exit_code`, with no traceback. The loader relies on that seam, so no command module adds a catch. The existing `except ValidationError` in `verify_finding` and `corpus_score` stay as they are.
- **Import `ReviewSessionPayload` inside the loader, not at the top of `session.py`.**: `session.py` imports it under `TYPE_CHECKING` only, so the loader needs a run-time import. A top-level import is not free: `python -X importtime -c "import devops_cli.ai.review_schema"` shows 1.68 s cumulative, and `import devops_cli.review.session` pulls none of it today. `session.py` is imported by `ui/data_providers.py`, `ai/review/pipeline.py`, `ai/review/runner.py` and `ai/review/exporter.py`. A function-level import keeps those imports as light as they are. `handoff.py` and `commands/review.py` already import the schema at the top, so the first call has no extra cost there.
- **Check the call sites with `git grep`, not with a test.**: A test of "all four readers use the loader" would read source text. The CLI test (task 2.1) shows the behavior of each reader, and the `git grep` in task 2.3 shows that no reader still calls `model_validate_json` itself.

## Rejected alternatives

- **Add try/except at each of the four call sites.**: Duplicates the formatting logic four times and leaves room for a fifth reader to miss the handler.
