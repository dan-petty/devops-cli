# Tasks

## 1. Guard Path.cwd in _resolve_git_dir

Reads: none. Changes: `src/devops_cli/telemetry/tracer.py`, `tests/test_tracer.py`.

- [ ] 1.1 Write a test that patches Path.cwd to raise FileNotFoundError, calls _resolve_git_dir(), and asserts it returns None with no exception. Write a second test that calls _resolve_git_dir with a valid start_dir containing a .git directory and asserts it returns that path, and verify that `uv run devops ci test tests/test_tracer.py` fails on the base
- [ ] 1.2 In _resolve_git_dir, replace current = (start_dir or Path.cwd()).resolve() with a try/except OSError block. When start_dir is None, attempt Path.cwd() inside the try block. On OSError, return None. When start_dir is provided, use it directly. The existing directory traversal logic remains unchanged, and verify that `uv run devops ci test tests/test_tracer.py` passes
- [ ] 1.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
