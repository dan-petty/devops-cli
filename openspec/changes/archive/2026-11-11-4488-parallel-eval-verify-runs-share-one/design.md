# Design

## Decisions

- **Put the unique store file helper in `src/devops_cli/core/repo.py`, next to `resolve_store_path`.**: That module already resolves a store name under the data directory, so the folder and the file name stay in one place and every eval command can call it.
- **Create the file with `tempfile.mkstemp`, then close its descriptor and keep the path for every later write.**: One standard-library call creates the file exclusively and gives a unique name, and the project uses the same call in `write_report`.
- **Take the time stamp of the name from the clock, and freeze the clock in the tests with time-machine.**: The project lists time-machine as a development dependency and docs/TESTING.md names it for a faked wall clock, so the helper needs no time parameter, and the name still shows when the run started.
- **Resolve the store folder inside the helper and create it with `mkdir(parents=True, exist_ok=True)` before `mkstemp`.**: `mkstemp` creates a file but not a missing directory, and the project's `write_report` makes the directory first for the same reason.
- **Replace the stamp line of the command with `resume or create_store_file(_STORE)`.**: `--resume` stays a plain path that creates no new file, and a run without it gets a new file; the existing command tests already prove the per-case write and the resume.
- **Test two runs that write at the same time through the command, with the second run on its own thread.**: The first run waits in its model call while the second run starts in the same frozen second and writes its report, which is the order of two parallel processes. A second run on the same thread meets the running event loop of the first run.
- **Leave the stage, screen and completeness eval commands unchanged.**: Their stamp comes after a long run, so the reported collision does not apply to them, and the shared helper is ready when one of them needs it.

## Rejected alternatives

- **Create the report file with `open(path, "x")` and a counter suffix after `FileExistsError`.**: It needs a retry loop and more code for the same result, while `tempfile.mkstemp` creates the file exclusively in one call at `src/devops_cli/roadmap/implement/implement_eval_run.py:457:tempfile.mkstemp(prefix=f"implement-{stamp}-"`.
- **Add `secrets.token_hex(3)` to the stamp, as `src/devops_cli/ai/run_store.py` does.**: A random suffix makes a collision unlikely but does not create the file exclusively, so two processes can still choose one name and replace each other's cases.
- **Change all four eval commands in this pull request.**: The issue reports the collision for `roadmap_eval_verify.py` only, and the other three take their stamp at the end of a long run, so changing them adds unproven work to this pull request.
- **Give the helper an optional moment for the test.**: It adds a parameter only for tests, while time-machine freezes the clock with no change to the code.
- **A new test module `tests/commands/test_roadmap_eval_verify_store.py`.**: The command tests already sit in `tests/roadmap/stage/test_roadmap_stage_verify_eval.py` with the fixtures they need, and docs/TESTING.md puts a new test in the file that already tests the behaviour.
