# Tasks

## 1. Add session fixture for heavy module imports

Reads: none. Changes: `tests/conftest.py`.

- [ ] 1.1 Write a test in tests/test_conftest_import_preload.py that asserts sys.modules contains pydantic_ai, anthropic, kubernetes, and textual after the session fixture runs, and that the fixture scope is 'session', and verify that `uv run pytest tests/test_conftest_import_preload.py -v` fails on the base
- [ ] 1.2 Add a session-scoped fixture in tests/conftest.py that imports pydantic_ai, anthropic, kubernetes, and textual. Name it _preload_heavy_modules. Use pytest.fixture(scope='session'). Import each module with importlib.import_module to avoid static analysis issues, and verify that `uv run pytest tests/test_conftest_import_preload.py -v` passes
- [ ] 1.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
