# Proposal

## Why

A test that starts a security scanner with no `scanner_fake` passes on the GitHub runner, where no scanner is on PATH, and fails in the devcontainer, where the scanners are installed (#4439). The required checks merge the bad test, and the next full local `devops ci` run fails. The change makes the floor show each refused program on every host, so such a test fails before the merge.

## What Changes

- The floor writes an executable stand-in for each name that `tests/support/refused_programs.py` returns into a directory under the run's temporary directory, and puts that directory first on PATH for the run.
- A test that starts `trivy`, `gitleaks`, `semgrep`, `gh` or any other refused program with no fake now finds it on every host, so the floor's `subprocess.Popen` refusal fails the test on the runner as it does in the devcontainer.
- `tests/commands/test_scan.py` gains a case that runs `scan trivy` with no `scanner_fake` and asserts a floor refusal, so the scan gives no `unavailable` result on any host.
- `tests/invariants/test_suite_refuses_real_programs.py` asserts that `shutil.which` finds each refused name in the floor's stand-in directory, which fails on the runner before the change.
- `scanner_fake` keeps its PATH replacement, so its scripted stand-in is the one `shutil.which` finds and the floor stand-in never runs; `tests/commands/test_scan.py:79: [Path(run.argv[0]).name for run in scanner_fake.runs],` and `tests/invariants/test_hermetic_floor.py:1037: assert len(paths) == 2` already assert it, so the plan adds no second case for it.
- No existing test changes its result: a test that reaches a refused program installs `process_fake`, which fakes the lookup, or `scanner_fake`, which replaces PATH, or sets its own PATH without the program, and `uv run devops ci test` is the census of group 1.
- `docs/TESTING.md` states the floor PATH rule and says that a test's own PATH still hides a program.
- The change has no spec delta: every changed path is under `tests/` or `docs/`, and no command, manifest or service behavior that a consumer observes changes.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Documents: `docs/TESTING.md`
- Tests: `tests/support/refused_programs.py`, `tests/conftest.py`, `tests/commands/test_scan.py`, `tests/invariants/test_suite_refuses_real_programs.py`

## Feasibility

- `read_file tests/support/refused_programs.py` showed `tests/support/refused_programs.py:15:def refused_programs() -> frozenset[str]:` and `tests/support/refused_programs.py:23:{CONST_GH_CLI, *(scanner.binary_name for scanner in scanners if scanner is not None)}`: the refused set is gh plus the binary of each scanner of the registry, read when the run starts.
- `read_file tests/conftest.py` lines 570-665 showed the two messages of the issue's log, `tests/conftest.py:610:f"process edge reached without a fake: {target} "` and `tests/conftest.py:652:msg = f"host path reached without a fake: {raw_path}"`, and the refusal `tests/conftest.py:614:pytest.fail(msg, pytrace=False)` inside `tests/conftest.py:def refuse_real_programs`.
- `read_file src/devops_cli/core/binaries.py` showed `src/devops_cli/core/binaries.py:13: return bool(shutil.which(name))`, and `read_file src/devops_cli/security/base.py` lines 380-410 showed `src/devops_cli/security/base.py:390: if not scanner._check_binary():` and `src/devops_cli/security/base.py:405: f"Binary '{scanner.binary_name}' not found on PATH",`: PATH alone decides whether a scan runs or reports the program missing.
- `read_file tests/commands/test_scan.py` lines 60-85 showed the scan call `tests/commands/test_scan.py:71: runner.invoke(scan_app, [sub, str(tmp_path), "--json"]).exit_code` and the scripted scanner `tests/commands/test_scan.py:68: scanner_fake.script("trivy", _CLEAN_TRIVY_RUN)`.
- `read_file tests/support/fakes/scanners.py` lines 300-330 showed `tests/support/fakes/scanners.py:318: "PATH", os.pathsep.join([str(fake.bin_dir), str(Path(sys.executable).parent)])`: `scanner_fake` replaces PATH with its stand-in directory and the interpreter directory.
- `read_file tests/invariants/test_hermetic_floor.py` lines 1020-1045 showed `tests/invariants/test_hermetic_floor.py:1037: assert len(paths) == 2` under a case named `test_scanner_fake_path_contains_only_stand_ins_and_interpreter`, so the floor entry is gone under the fake.
- `read_file tests/support/fakes/process.py` lines 450-470 showed `tests/support/fakes/process.py:463: monkeypatch.setattr(shutil, "which", fake_which)`: a test with `process_fake` never sees PATH.
- `read_file tests/support/host_paths.py` lines 50-80 showed `tests/support/host_paths.py:68: Path(tempfile.gettempdir()).resolve(),` in `tests/support/host_paths.py:def allowed_host_roots`, so the run's temporary directory is allowed to the host path guard and the stand-ins there pass it.
- `read_file tests/invariants/test_suite_refuses_real_programs.py` showed `tests/invariants/test_suite_refuses_real_programs.py:22:@pytest.mark.parametrize("program", sorted(refused_programs()))` and `tests/invariants/test_suite_refuses_real_programs.py:28: with pytest.raises(pytest.fail.Exception, match=f"real {program}"):`: the module owns the subject, and the refusal is asserted through `pytest.fail.Exception`, which no `except Exception` catches.
- `read_file src/devops_cli/security/registry.py` lines 1-30 showed `src/devops_cli/security/registry.py:18: """Instantiate the 13 built-in security scanners."""`, and the refused set takes one `binary_name` from each scanner the registry returns, so a scanner added to the registry gets a stand-in with no list to edit.
- The count of the refused set is unverified: no tool of this run counts it, so the plan gives one stand-in for each name that `refused_programs()` returns, `uv run devops ci test` is the `verify` of group 1, and the step stops and returns the item when its result differs from this plan. No member is removed, restricted or allowlisted: each is a program that the floor refuses, because gh acts as the developer's own login and a scanner fetches rule packs and advisories from a child process.
- `read_file tests/security/test_sbom.py` lines 88-100 showed `tests/security/test_sbom.py:96: monkeypatch.setenv("PATH", str(empty_bin))`, and `read_file tests/commands/test_scan_outcomes_and_gating.py` lines 128-140 showed `tests/commands/test_scan_outcomes_and_gating.py:135: monkeypatch.setenv("PATH", str(tmp_path / "no-programs"))`: a test that needs a program missing replaces PATH, so the floor entry is off PATH for it.
- `references refused_programs` listed four files, `tests/invariants/test_suite_refuses_real_programs.py`, `tests/support/__init__.py`, `tests/support/refused_programs.py` and `docs/TESTING.md`; three are in the `changes` of groups 1 to 4, and `tests/support/__init__.py` stays unchanged by the decision and the `references` entry that record it.
- `read_file docs/TESTING.md` showed `docs/TESTING.md:80:No test starts a real security scanner either: a scanner fetches rule packs and advisories from a child process the network block does not see.`, `docs/TESTING.md:265:the refusal to start a real gh or security scanner` and `docs/TESTING.md:280:a test that needs a scanner missing gives it a PATH without the program`, which are the three places that group 4 edits.
- `read_file tests/commands/test_scan.py` lines 60-85 showed its imports of `pytest`, `CliRunner` and `scan_app`, which the new case needs, and its module-level `_CLEAN_TRIVY_RUN`.
- Probe line, word for word: The path `tests/support/refused_programs.py` is a file of the staging commit.
- Probe line, word for word: The path `tests/commands/test_scan.py` is a file of the staging commit.
- Probe line, word for word: The path `docs/TESTING.md` is a file of the staging commit.
- Probe line, word for word: The path `shutil.which` is no file of the staging commit. No commit in the history deleted or renamed it. That is expected: it is a standard-library function, not a path.
- Probe line, word for word: The path `subprocess.Popen` is no file of the staging commit. No commit in the history deleted or renamed it. That is expected for the same reason.
- Probe line, word for word: Not probed, the bound of 10 commands is reached: `tests/invariants/test_suite_refuses_real_programs.py`, `that.refused`, `scanner_fake`, `trivy`, `gitleaks`, `semgrep`, `unavailable`, `None`. This run read `tests/invariants/test_suite_refuses_real_programs.py` itself and found it a file of the commit.
- The runner half of the premise is not checked: no tool of this run read the `Tests & Coverage` job of `.github/workflows/ci.yml`, so that the job installs no scanner is the issue's report and not a finding of this run.
- No function that the plan calls needs a checkout of the repository, a client of a service or a network: `shutil.which` reads PATH, `tmp_path_factory.getbasetemp` reads the run's temporary directory, and `Path.write_text` and `Path.chmod` write under it.
- The plan introduces no command and no verify program of its own. `uv run devops ci test` needs a checkout, no client and no network, with the failure classes `test`, `timeout` and `ci_infra`; `uv run devops ci docs` needs a checkout, no client and no network, with the failure class `lint`.
- Both verify commands need the runner capabilities `uv`, `python`, `pytest` and `git`, each in the image, under the pod settings `readOnlyRootFilesystem: true` and `runAsNonRoot: true`. No program of this plan is `NOT_IN_RUNNER`: the stand-ins are shell scripts that the floor refuses before any start, and the suite starts no scanner.
- The context lists no overlap, no metric sender and no issue dependency, and `find_issues` for `refused_programs PATH floor` returned only #4439 itself, so the plan depends on no open item. #4321 is closed, and the staged tree holds its scripted scanners, as `tests/commands/test_scan.py:68: scanner_fake.script("trivy", _CLEAN_TRIVY_RUN)` shows.

## Existing Tool Considered

No open, maintained tool covers a project-specific pytest floor that makes a refused program visible on every host; the change builds the helper and the fixture itself, at about 2,000 tokens to write, 1,000 tokens to keep and fix, and about 1 hour elapsed.

## Dependencies

None.
