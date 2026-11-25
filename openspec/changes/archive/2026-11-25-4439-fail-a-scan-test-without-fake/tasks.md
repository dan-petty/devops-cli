# Tasks

## 1. Write a stand-in for each refused program and put it first on PATH

Kind: other. Reads: `tests/support/refused_programs.py`, `tests/conftest.py`, `tests/support/host_paths.py`, `tests/support/fakes/scanners.py`. Changes: `tests/support/refused_programs.py`, `tests/conftest.py`.

- [x] 1.1 In `tests/support/refused_programs.py`, add the constant `REFUSED_STAND_IN_DIRNAME` with the value `refused-program-bin` and the function `stand_in_directory(directory: Path) -> Path`. It makes the directory, writes for each name that `refused_programs()` returns the file `directory / name` with the two lines `#!/bin/sh` and `exit 127`, sets mode 0o755, and returns the directory. In `tests/conftest.py`, add the session-scoped autouse fixture `refused_program_stand_ins(tmp_path_factory)` beside `tests/conftest.py:def refuse_real_programs`. It calls `stand_in_directory(tmp_path_factory.getbasetemp() / REFUSED_STAND_IN_DIRNAME)`, puts that path first on `os.environ["PATH"]`, and restores the earlier value in a `finally`. Leave `tests/support/fakes/scanners.py` unchanged, because `scanner_fake` replaces PATH with its own directory and the interpreter directory
  - Verification: `$ uv run devops ci test` passes

## 2. Fail a scan that runs with no scanner_fake

Kind: other. Reads: `tests/commands/test_scan.py`, `tests/support/fakes/scanners.py`, `tests/conftest.py`. Changes: `tests/commands/test_scan.py`.

- [x] 2.1 Add `test_a_scan_without_a_scanner_fake_fails_at_the_floor` to `tests/commands/test_scan.py`, beside `tests/commands/test_scan.py:71: runner.invoke(scan_app, [sub, str(tmp_path), "--json"]).exit_code`. It takes `tmp_path`, `runner` and `unexpected_loopback_connects`, marks `cached_default_ruleset` with `pytest.mark.usefixtures`, runs `runner.invoke(scan_app, ["trivy", str(tmp_path), "--json"])` with no `scanner_fake`, and asserts inside `pytest.raises(pytest.fail.Exception, match="without a fake")` that the floor refuses the run, clearing `unexpected_loopback_connects` in a `finally`. The match holds both floor messages, so the case also passes on a workstation whose installed scanner the scan reaches first. Add no second `scanner_fake` case, because `tests/commands/test_scan.py:79: [Path(run.argv[0]).name for run in scanner_fake.runs],` already asserts that each scanner runs from the fake's stand-in
  - Verification: `$ uv run devops ci test tests/commands/test_scan.py` passes

## 3. Assert the floor finds each refused program

Kind: other. Reads: `tests/support/refused_programs.py`, `tests/invariants/test_suite_refuses_real_programs.py`, `tests/invariants/test_hermetic_floor.py`. Changes: `tests/invariants/test_suite_refuses_real_programs.py`.

- [x] 3.1 In `tests/invariants/test_suite_refuses_real_programs.py`, add `test_each_refused_program_is_found_on_the_floor_path`, parametrized over `sorted(refused_programs())` as `tests/invariants/test_suite_refuses_real_programs.py:22:@pytest.mark.parametrize("program", sorted(refused_programs()))` is. It takes `tmp_path_factory` and asserts that `shutil.which(program)` is the file `tmp_path_factory.getbasetemp() / REFUSED_STAND_IN_DIRNAME / program`. Import `shutil` and `Path`, and `REFUSED_STAND_IN_DIRNAME` from `tests/support/refused_programs.py`. The case fails on the runner before the change, where `shutil.which` finds nothing, and passes on every host after it
  - Verification: `$ uv run devops ci test tests/invariants/test_suite_refuses_real_programs.py` passes

## 4. State the floor PATH rule in the testing document

Kind: other. Reads: `docs/TESTING.md`. Changes: `docs/TESTING.md`.

- [x] 4.1 In `docs/TESTING.md`, extend line 80 ("No test starts a real security scanner either: a scanner fetches rule packs and advisories from a child process the network block does not see.") with the floor rule: the floor writes an executable stand-in for each name that `refused_programs()` returns, first on PATH, so `shutil.which` finds the program on every host and a test with no fake fails on the runner as it does on a workstation. Add the floor PATH to the list of the floor beside line 265 ("the refusal to start a real gh or security scanner"), and say beside line 280 ("a test that needs a scanner missing gives it a PATH without the program") that a test's own PATH replaces the floor entry
  - Verification: `$ uv run devops ci docs` passes
