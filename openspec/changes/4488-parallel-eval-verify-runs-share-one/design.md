# Design

## Decisions

- **Put the unique store file helper in `src/devops_cli/core/repo.py`, next to `resolve_store_path`.**: That module already resolves a store name under the data directory, so the folder and the file name stay in one place and every eval command can call it.
- **Create the file with `tempfile.mkstemp`, then close its descriptor and keep the path for every later write.**: One standard-library call creates the file exclusively and gives a unique name, and the project uses the same call in `write_report`.
- **Give the helper an optional moment, and use it as the prefix of the file name.**: The test passes one fixed moment twice, so it proves the same-second case with no clock patch and no model call, and the name still shows when the run started.
- **Resolve the store folder inside the helper and create it with `mkdir(parents=True, exist_ok=True)` before `mkstemp`.**: `mkstemp` creates a file but not a missing directory, and the project's `write_report` makes the directory first for the same reason.
- **Route the command through a `_report_target` function that returns the resume path or a new store file.**: The command's report path becomes one function that an offline test can call twice, and `--resume` stays a plain path that creates no new file.
- **Leave the stage, screen and completeness eval commands unchanged.**: Their stamp comes after a long run, so the reported collision does not apply to them, and the shared helper is ready when one of them needs it.

## Rejected alternatives

- **Create the report file with `open(path, "x")` and a counter suffix after `FileExistsError`.**: It needs a retry loop and more code for the same result, while `tempfile.mkstemp` creates the file exclusively in one call at `src/devops_cli/roadmap/implement/implement_eval_run.py:457:tempfile.mkstemp(prefix=f"implement-{stamp}-"`.
- **Add `secrets.token_hex(3)` to the stamp, as `src/devops_cli/ai/run_store.py` does.**: A random suffix makes a collision unlikely but does not create the file exclusively, so two processes can still choose one name and replace each other's cases.
- **Change all four eval commands in this pull request.**: The issue reports the collision for `roadmap_eval_verify.py` only, and the other three take their stamp at the end of a long run, so changing them adds unproven work to this pull request.
- **Patch `datetime` in the command and run the whole command twice in the test.**: That test needs a model fake and a checkout, while an optional moment on the helper proves the same-second case offline, as the existing tests of `tests/core/test_core_repo.py` do.
