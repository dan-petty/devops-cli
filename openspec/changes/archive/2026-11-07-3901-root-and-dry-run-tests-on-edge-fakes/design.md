# Design

## Context

See proposal.md for the motivation and the scope (#3901, item 3 of #1333). The process fake is #775. The `cli` fixture is #1310.

## Decisions

### 1. The root tests run real commands
- **Decision**: a test of the global `--dry-run` flag runs a real command through the `cli` fixture, and reads the output and the calls of `process_fake`. `tf apply` shows the difference between a dry run and a run: a dry run starts no program, and a run starts `tofu apply`.
- **Rejected**: keep a double of `main._delegate` that records the forwarded arguments. It checks the argument list that no person sees. A forwarding defect shows in the plan of the real command, such as the `--dry-run` after `--` that makes `sandbox deploy` run `echo test --dry-run`. The mutation `flag appended at the end` fails the new test and passed the old one only because the old one compared a list.
- **Rejected**: a fake of the lazy command proxy in `tests/support/fakes/`. The proxy is code inside the process, and ADR 0007 fakes edges only.

### 2. The stub command module is registered through `add_typer`
- **Decision**: a fixture of `test_global_dry_run.py` calls `devops_cli.main.app.add_typer("tests.support.dry_run_stub:app", name="stub")` and removes the registered command after the test. `tests/support/typer_commands.py` already describes this pattern, and `tests/ai/mcp/test_dispatcher_contract.py` uses it.
- **Rejected**: a real command with no dry-run class, taken from `tests/fixtures/dry_run_gaps.json`. The list shrinks, and each command that leaves it would break the test. This is why the stub exists.
- **Rejected**: a new `CliRunner` on a root app that the test builds. The convention says a CLI test uses the `cli` fixture.

### 3. The tests of `entry.main` run the real app
- **Decision**: `entry.main` raises `SystemExit`, because Typer runs in standalone mode. The tests use `pytest.raises(SystemExit)`, read `capsys` and the process fake, and read the dry-run state through the public `is_dry_run` and `in_dry_run_invocation`.
- **Rejected**: patch `devops_cli.main.app`. The patch hides the root callback, which is the code that decides the state after the run.

### 4. The decorator tests read the printed result
- **Decision**: the decorator prints a JSON result. The tests parse it and compare the whole object. The failure of the print is made by a detail that Pydantic cannot serialize. The state during the print is read by the serializer of a Pydantic model that the test defines.
- **Rejected**: patch `render_dry_run_result` to raise or to record. A patch of a `devops_cli` name is the thing this item removes.

### 5. The printed result is a snapshot
- **Decision**: `render_dry_run_result` prints text whose whole form is the contract, so its test is a syrupy snapshot (`docs/TESTING.md`, Test data).
- **Rejected**: assert a substring, as the old test did (`"dry-run" in out or "devops repos sync" in out`). It passed for almost any output.
