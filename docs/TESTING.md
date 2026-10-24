# Testing

The vocabulary devops-cli's tests are designed and organised in, and the conventions every test follows. [ADR 0007](adr/0007-tests-double-only-process-edges.md) records why tests double only edges.

## Vocabulary

### Test doubles

**Edge**:
A point where devops-cli reaches beyond its own process to something a test must not touch for real: another machine, a long-lived daemon, a program other than git, bwrap or kubectl's offline renderers, the keyring, or the wall clock.
_Avoid_: boundary, external dependency, integration point

**Seam**:
The one place in devops-cli that supplies an edge's real implementation, and where a test installs a fake instead.
_Avoid_: hook, injection point, patch target

**Fake**:
A working in-memory stand-in for one edge that answers like the real thing and records what it was asked.
_Avoid_: mock, stub, dummy, test double

**Contract suite**:
One set of tests run against both a fake and the real implementation of its edge, the real side against recorded responses or a local tool, never a live service.
_Avoid_: parity tests, conformance tests

### Isolation

**Hermetic floor**:
The isolation every test runs inside, whatever its package: no edge reached without a fake, process-wide state reset after it, its own data directory, config and gh config, a throwaway kubeconfig for the run, and no way onto the session bus.
_Avoid_: global fixtures, autouse setup

**Live test**:
A test that runs a real local tool the host may lack, such as bwrap, and is skipped only where that tool is missing.
_Avoid_: system test, host test

### Kinds of test

**CLI test**:
A test that drives a `devops` command and checks only what the command layer owns: argument parsing, wiring, output and exit code.
_Avoid_: command test, end-to-end test

**Invariant test**:
A test whose subject is a committed file of this repository (the source tree, docs, change folders, workflows, manifests or dashboards) rather than the behaviour of devops-cli.
_Avoid_: architecture test, hygiene test, consistency test

**Ratchet**:
An invariant test that holds a count of something being retired to a ceiling that may only go down.
_Avoid_: ceiling test, baseline, allowlist

### Test data

**Builder**:
A function that makes one valid domain object from defaults, named after its [CONTEXT.md](../CONTEXT.md) term.
_Avoid_: factory, fixture, helper

**Snapshot**:
The stored expected text of an output whose whole text is the contract, such as a command's output, a rendered manifest or a prompt. It is regenerated, never edited by hand.
_Avoid_: golden file, golden

## Conventions

Every new test follows these rules. Some of them name a path, fixture or check that does not exist yet; each such name is marked *(target)*, and [Until the migration ends](#until-the-migration-ends) says what exists today and what a new test does meanwhile.

### Doubles

- A test doubles only edges. Everything inside the process runs for real.
- **Faked edges**: every program except git, bwrap and kubectl's offline renderers (gh, the rest of kubectl, helm, minikube, the docker and podman CLIs, the scanners, and `uv run devops` calling itself), with the lookup of the program on PATH part of its fake; all network, meaning HTTP on any client stack, raw sockets and DNS; GitHub's API, through the GitHub session; model and embedding providers; the Kubernetes API; the Docker engine; Valkey; Qdrant; outbound MCP servers; OTLP export; the keyring and D-Bus.
- **Real**: the filesystem under `tmp_path`; environment and config, through the hermetic floor and the `config` fixture; git in temporary repositories; kubectl's offline renderers, `kubectl kustomize` and `kubectl patch --local`, which read only files and reach no cluster; bwrap in live tests; in-process servers, such as FastAPI's `TestClient` and loopback servers; randomness; host identity; and stdin, through `CliRunner(input=...)`.
- No test starts a real gh, which would act as the developer's own login: a gh command a test reaches goes to a fake, and the floor fails a test that starts gh.
- No test starts a real security scanner either: a scanner fetches rule packs and advisories from a child process the network block does not see. The floor refuses gh and the binary of every scanner the security scanner registry holds, names `tests/support/refused_programs.py` reads from the registry when the run starts, so a scanner added there is refused with no list to edit. The refusal sits at `subprocess.Popen`, beneath every seam, and fails the test with `pytest.fail`, which no `except Exception` in the code under test hides. A test whose code starts a scanner asks for `scanner_fake`, which answers the scanner's request to the tool executor with the scanner's run recorded from the real tool.
- No test starts sudo, which changes the host, or uv installing or syncing from PyPI, and the floor refuses both. The gate's own `uv audit`, `npm audit`, `uv tree --outdated` and `uv check` are its intended network checks, run by `devops ci`, never by a test.
- Each edge has one seam in `src/devops_cli`: a Protocol, plus the one place that supplies the real implementation *(target for most edges)*. The clock's seam is the sleep and clock parameters the libraries take, with no Protocol, as [Clock](#clock) describes. A test installs the edge's fake through the seam's fixture, or through a constructor or parameter the domain code already takes.
- Each edge has one fake, in `tests/support/fakes/<edge>.py`, shared by every test that reaches the edge. A test does not build its own double of an edge.
- Every fake has a contract suite, run against the fake and against the real implementation over recorded responses or a real local tool, never a live service. A fake without a contract suite does not merge.
- Patching a stdlib or SDK object itself, such as `subprocess.run` or `time.sleep`, is a fallback for stdlib edges only.
- No test patches a devops-cli module, class, function or attribute, and no test imports a private name (one that starts with `_`) from `devops_cli`. A test reaches private code through the public interface that uses it.
- Product code holds nothing for tests: no `unittest.mock`, no `PYTEST_CURRENT_TEST` check, no check for a mock's attributes, and no module shaped so that a test can patch it. Fakes, and in-memory implementations that production does not use, live in `tests/support/` and never ship in the wheel.

### Layout

- `tests/` mirrors the package tree of `src/devops_cli` at full depth *(target)*: the tests of `src/devops_cli/ai/review/` sit in `tests/ai/review/`. Each package directory has its own `conftest.py` for that package's fixtures.
- A package is tested through its public interface, in one file per behaviour, named after the behaviour, such as `tests/roadmap/test_duplicate_candidates.py` *(target)*; not in one file per source module. A test of behaviour that crosses packages goes to the package that owns the behaviour.
- A file is never named after the work that produced it: a review session, an issue, a pull request, a batch or a hardening pass. A regression test joins the file of the behaviour it pins.
- `tests/invariants/` *(target)* is the only place for test files outside the mirror. It holds the invariant tests, one file per subject: `test_source_tree.py`, `test_agents_md.py`, `test_change_folders.py`, `test_workflows.py`, `test_k8s_manifests.py` and `test_grafana_dashboards.py`. A new invariant test goes into its subject's file, created if absent, never into a parallel file.
- `tests/support/` holds what tests share, and no test module or conftest lives in it, which the registration enforces: the fakes in `fakes/<edge>.py`, the builders in `builders.py`, and shared fixtures. Every submodule and subpackage under it is registered as a plugin, so a fixture added there needs no conftest edit: the root conftest's one `pytest_plugins` entry names `tests.support.bootstrap`, which isolates HOME and then registers the rest, so a support module that imports devops-cli binds its paths under the isolated HOME. The root conftest marks `tests.support` for assertion rewriting first and imports it only inside functions, and `PytestAssertRewriteWarning` is an error, so a support module imported too early fails the run. A support module defines no `pytest_*` name that is not a hook, and defines each fixture it registers with `pytest.fixture` rather than importing another module's or handing one out by a module-level `__getattr__`: the registration fails a run whose support module holds a fixture or hook its source does not show. An invariant holds the top level and the class bodies of every helper module under `tests/` to docstrings, imports at the top level, defs, classes, assignments to names alone and `if TYPE_CHECKING:` blocks with no `else`; the values bound to names, decorators, default arguments, base classes and metaclasses still run on import unchecked. A module imports from a support module with `from tests.support[.x] import ...`, and no module but `bootstrap` holds `tests.support` or a package under it, which another invariant enforces, so none reads a support module it does not import.
- A test finds the repository root and its test data through `tests.support.paths`: `REPO_ROOT`, `TESTS_ROOT`, `FIXTURES` (`tests/fixtures/`) and `GOLDEN` (`tests/golden/`). It never builds a path from its own `__file__`, so it reads the same paths at any depth.
- A test file imports what it shares from `tests/support/`, never from another test file or from a conftest. One check over every Python file under `tests/` but `tests/fixtures/` fails the full gate on a module that reads `__file__` outside `tests/support/` or imports a test module or a conftest, naming each as `path:line`: an imported module under `tests`, or a top-level one, is a test module when pytest collects its file by the `python_files` patterns; `from X import n` imports the module `X.n` when `X` is a package or `X/n.py` exists; and a relative import is resolved against the importing module's package, one past the top-level package being reported too. It lives alone in `tests/test_test_module_independence.py`, which no change to a source or helper module selects, as the next section says.
- The root `tests/conftest.py` holds only the hermetic floor *(target)*. Domain fixtures live in their package's conftest or beside their fake.

### Names and assertions

- A test is named after the behaviour it checks, in [CONTEXT.md](../CONTEXT.md) glossary terms: `test_blocked_item_is_not_started`. The name never names a helper, a private function or a double, and it uses the glossary term, never a word the glossary lists under _Avoid_.
- An assertion compares whole values: `assert result == expected` against a complete expected model, or `assert fake.requests == [...]` for what an edge was asked.
- A test of an error path checks the `DevOpsCLIError` subclass raised, with its exit code and machine-readable error code.
- Tuple equality is only for picking fields out of an object whose other fields are noise, such as generated ids or timestamps.
- Consecutive asserts are fine. Ruff's C901 does not count them, so they do not raise a test's complexity.

### CLI tests

- A CLI test invokes a command through the shared `cli` fixture, not through a `CliRunner` it builds itself.
- It checks only what the command layer owns: argument parsing, wiring, output and exit code. Every CLI test sits in `tests/commands/` *(target: a few do today)* and reaches edges only through its fakes.
- A domain rule is tested once, through its domain package. Logic behind a private helper in `commands/` moves into its domain package behind a public function and is tested there, and the command becomes a thin adapter. Until it moves, it is tested through the CLI with edge fakes.

### Config

- A test sets configuration through the `config` fixture. The fixture writes the overrides into the test's own `config.yaml`, the file `DEVOPS_CLI_CONFIG` names, and resets the settings cache.
- No test patches `load_settings` or `CONFIG_PATH`.

### Test data

- A test builds a domain object with a builder: one per glossary term, named after it (`make_finding`, `make_verdict`, `make_item`, `make_candidate`), in `tests/support/builders.py`. A builder is a plain function that builds a valid object through the real constructor or parser, with its validation, from valid defaults, and takes keyword-only overrides; a model's builder refuses a key that is no field of the model with `TypeError` naming it, so a typo or an alias fails rather than being dropped.
- An output whose whole text is the contract, such as a command's output, a rendered manifest or a prompt, is checked against a snapshot that syrupy stores. Any other expected value is a literal written in the test. A Pydantic model is snapshotted through `model_dump()` or syrupy's Amber Pydantic plugin.
- A snapshot is regenerated, never edited by hand, with `uv run pytest <test-file> --snapshot-update --snapshot-file-lock`, and the commit says why it changed. The file lock is required: without it, an update under xdist can lose entries from a shared `.ambr` file ([syrupy issue 1237](https://github.com/syrupy-project/syrupy/issues/1237)).

### Hosts, sockets and the shared container

- A mock host is `example.com`, with no subdomain.
- Bandit scans `tests/` (`devops ci security`). A test binds a socket to `127.0.0.1` or `::1`, and writes under `tmp_path`. Use `# nosec BXXX` only on a literal that the test examines.
- No test sets `RLIMIT_NPROC`, which Linux counts for every process of the user in the container, and no test starts processes without a bound ([ARCHITECTURE.md](../ARCHITECTURE.md), section 7).

### Property tests

- State machines, such as the roadmap lifecycle, and pure functions over open-ended input, such as parsers, policy evaluation and redaction, are tested with Hypothesis properties.
- Everything else is tested with examples.

### Clock

- Wall-clock reads are faked with time-machine *(target)*. freezegun is not used: it is unmaintained, and its frozen monotonic clock hangs asyncio and tenacity.
- Waiting goes through the sleep and clock parameters the libraries already take, such as tenacity's `sleep=` and the `sleep` of pydantic-ai's retry configuration, and one place in `src/devops_cli` supplies the real ones *(target)*. A direct `time.sleep` is patched at the stdlib, the fallback for stdlib edges. devops-cli has no Clock type of its own.
- No test bounds elapsed wall-clock time from above. A loaded machine stretches the time, and the bound then fails correct code. A test shows the behaviour without the clock: it waits for the event (next section), counts something that the run decides, or asserts on the waits of the `clock` fixture. An operation that does not stop fails at the hang bound of pytest-timeout. A budget counts something the run decides: the startup budget in `tests/test_cli_startup_imports.py` counts the modules that `--version`, the root `--help` and a few commands' `--help` import, and fails on any heavy module that any command group's `--help` imports, never on seconds. Each argv starts one fresh interpreter, and every check on that argv reads that one run.
- The ast-grep rule `test-elapsed-upper-bound` in `.ast-grep/rules/` holds `tests/` to this. Elapsed time is a clock reading minus an earlier time, and remaining time is a time minus a clock reading. A clock reading is a call of the `time` or `datetime` module that reads the current time, or a local name bound to one. The rule fails an assert that bounds elapsed time from above or remaining time from below, in the assert itself or through a local name. The `constructs` row of `devops ci` and the `ast-grep-scan` commit hook run it. A lower bound, such as a contract case that shows a real wait lasts at least its duration, holds on a loaded machine, and the rule allows it.

### Waiting for another thread

- A test that waits for something another thread or process does waits with `THREAD_HANDOFF_BOUND_SECONDS` from `tests/support/waits.py`, through `Event.wait`, `Queue.get`, `Thread.join`, `Barrier(timeout=...)` or `wait_until`, never with a deadline of its own. The wait returns as soon as its event happens, so only a failing test waits the bound out; a 1 or 2 s deadline failed correct code while a loaded host kept a ready thread waiting for a CPU.
- Anything a test relies on to stay alive or blocked, such as a sleeping child process or a job held until the test releases it, outlives the bound of every wait that observes it, or records whether the test ended it and asserts that it did. A hold on its observer's bound runs out inside the observer's window, and the test passes with the bug it checks for.
- A wait that checks that nothing happens keeps a short window of its own, opened only after a bounded, asserted wait shows the competing thread has reached the point where the event would happen. A comment at the window says so.
- A Textual test waits through its pilot. `pilot.press` and `pilot.pause()` return once the app has handled what was queued and the process has gone idle. A state the app reaches later is read again every `POLL_INTERVAL_SECONDS`, with `pilot.pause(POLL_INTERVAL_SECONDS)` between reads, under `THREAD_HANDOFF_BOUND_SECONDS`, never with `wait_until`, which would block the event loop the app runs on. The root conftest turns Textual's animations off (`TEXTUAL_ANIMATIONS=none`), so no wait sits out an animation.
- Every test runs under pytest-timeout's per-test bound, `timeout` in `[tool.pytest.ini_options]`, with `timeout_method = "signal"`, so a test that hangs fails in its own process, naming itself, and the run and its xdist worker carry on. The bound is a hang bound, far above the slowest test on a loaded host and above every wait's bound; a test that needs longer says so with `@pytest.mark.timeout(<seconds>)`.

### Which tests a narrowed run selects

- `devops ci test <paths>` runs only the tests a change reaches, and so does `devops test run --changed`, over the files changed since the branch left `main`, committed or not. A test module is reached when it is named for a changed module, at any depth, or imports it. A test module that only sits in the directory mirroring the module's package is not reached.
- Given no `-n`, a narrowed `devops ci test` runs serially for up to `DEFAULT_CI_TEST_SERIAL_MAX_FILES` test modules, where starting xdist workers costs more than it saves, and on `DEFAULT_CI_TEST_NARROWED_WORKERS` workers above that; the full suite, and the fallback to it, run on `addopts`' `-n logical`. Any run with workers distributes its tests with `addopts`' `--dist worksteal`: a worker that runs out of tests takes half the tests another worker has not started, so a block of slow tests handed to one worker late in the run no longer keeps the others waiting for it. It runs pytest in a session of its own, so a timeout, Ctrl-C, SIGTERM or SIGHUP stops pytest and its workers with `uv`: a timeout with SIGTERM, a signal by first forwarding the SIGINT a terminal would have sent, so pytest runs its teardown, then SIGTERM and SIGKILL, which a second signal brings forward and cannot skip. A test that drives `devops ci test` doubles `asyncio.create_subprocess_exec` with `record_spawns` from `tests/support/session_spawns.py`, and asks for `refuse_nested_test_runs`, which fails any real `uv` or pytest it would start.
- With a fresh coverage index (`devops ci coverage --build-index`), `devops ci test` selects the test modules that executed each changed module the index holds, in place of name-and-import matching. A module the index does not hold, a missing or stale index, and `devops test run --changed` select by name and import. So a test that should run for a module executes the module's code inside the test, not only on import, and names the module or imports it.
- A change that can alter tests that never import it runs the whole suite: `conftest.py`, `pyproject.toml`, `uv.lock`, `.python-version`, and a helper module under `tests/` that reaches every test, as the next rule says. `devops ci test`, and so the commit hook, runs the whole suite for any `conftest.py` it is given, at any depth, and under `--no-fallback` refuses any of these files instead. `devops test run --changed` narrows a conftest below `tests/`: one that only defines fixtures selects its own directory, and one that binds a `pytest_*` hook, which pytest calls for every test, selects the whole suite.
- A helper module is a Python file under `tests/` that is neither a test module nor a conftest, the modules of `tests/support/` included. One reaches every test when it defines a fixture or binds a `pytest_*` name, or when a conftest or such a helper imports it, directly or through other modules, inside a function too; and when it is deleted, renamed away or cannot be read, since what it registered can no longer be known. Any other helper selects the test modules that import it, directly or through other modules, and a package's `__init__.py` those importing any of the package's modules. `devops test run --changed` lists a rename as its old path deleted and its new path added, so a helper renamed away reaches every test. The registration fails a run whose support module holds a fixture or hook this rule cannot see in its source, such as one made by a decorator factory or imported under a new name.
- A check that parses every file under `tests/`, as the check against `__file__` and test-module imports does, runs only in the full gate: its module imports nothing from devops-cli and no module under `tests/`, spells no devops-cli module's dotted name and is named for none, so no change to a source or helper module selects it, and a narrowed run reaches it only when given its module or when it runs the whole suite (`tests/test_test_selection.py` checks both). With a coverage index, every test module is credited with what the root conftest's function-scoped autouse fixtures run in its setup and teardown, so a change to one of those modules selects the check's module with every other test module.
- A narrowed run does not see what a helper does on import to tests that do not import it. The invariant above refuses every top-level or class-body statement but those that bind names, and what still runs unchecked, a value bound to a name, a decorator, a default argument, a base class or a metaclass, is caught by the full gate, the pre-push `uv run devops ci`, not by the narrowed run.
- The commit hook runs `devops ci test` on the staged Python files only, so `pyproject.toml`, `uv.lock` and `.python-version` never reach the whole suite through it. They do when given to `devops ci test` or listed by `devops test run --changed`, and through the pre-push `uv run devops ci`. Nor does the hook get a deleted path or a rename's old path: without a coverage index that knew the helper, a test module still importing its old name runs only in the full gate; with one, the index drift finds the gone helper and the hook runs the full suite.
- A trigger file that changed only since the coverage index was built leaves the index stale, and `devops ci test` selects by name and import until the index is rebuilt. A helper module the index knew that is gone runs the whole suite instead, or is refused under `--no-fallback`.

### Coverage

- The coverage gate stays at 90% (`fail_under` in `pyproject.toml`).
- A line that no public behaviour reaches is dead code. It is deleted, not covered by a test that reaches past the public interface.

### Floor and ratchets

- Every test runs inside the hermetic floor, which the root conftest supplies: the network block, which also refuses a loopback connect to a port no socket in the test process binds and fails the test that made it, even when the code under test swallowed the refusal; the refusal to start a real gh or security scanner; the test's own data directory, config and gh config, with no way onto the session bus; a pinned GitHub identity, so a gh or git child gets a placeholder token, never the developer's login; a throwaway kubeconfig for the run; the config write guard, which fails a test when it opens a config file for writing, renames a file onto one or removes one outside the run's temporary directory, and names the test and the stack; and the workspace tripwire, which fails the run when a test writes to the workspace's `config.yaml` or to a tracked file.
- The floor fails a test that reaches a faked edge without its fake, with an error naming the edge.
- A test that checks a service that is down refuses it through `refusing_port`, a loopback port the test binds and never listens on, so the kernel refuses each connect as a stopped service would, and the service's retry waits return at once, as [Clock](#clock) says. A test that needs a service's answers fakes it at its edge, such as the model through `model_fake`.
- After every test, the floor calls the public reset of every process-wide cache and singleton, and an invariant test fails a module-level cache or `global` in `src/devops_cli` that has no reset there.
- Telemetry export and the Valkey cache, best-effort side channels that nearly every test reaches, go to a loopback port the floor binds for the run, `unserved_side_channel_port`, which refuses them as a workstation that serves neither does.
- Telemetry export is off unless a test opts in with the OTLP fake *(target)*.
- Ratchets hold each thing being retired to a ceiling that may only go down: `test_suppressions_stay_under_their_ceilings` in `tests/test_architectural_invariants.py` holds the suppression comments, the `# noqa: C901` markers among them, and `tests/test_swallowed_failures_ratchet.py` the swallowed failures. Patches aimed at devops-cli, imports of its private names, test accommodations in product code (`unittest.mock`, `PYTEST_CURRENT_TEST` and mock-attribute checks) and test files outside the layout get ratchets of their own *(target)*. A change that passes a ceiling is fixed, and the ceiling is never raised; a ratchet at zero becomes a ban.

### Until the migration ends

The suite moves to these conventions package by package ([ADR 0007](adr/0007-tests-double-only-process-edges.md)). Until the move is done:

- **Exists today**: the network block, with its failure of a test that connects to a loopback port or `AF_UNIX` socket the test process does not bind or looks up an external DNS name, the `refusing_port` double and the side-channel port; the floor's default deny of processes (every program except git, bwrap and kubectl's offline renderers, with `@pytest.mark.live` for live local tools) and of the keyring (`_DenyKeyring` installed before the first test); the reset of every piece of process-wide state in `src/devops_cli` after each test, guarded by an invariant test; telemetry export off by default unless a test opts in through `config`; the `cli` and `config` fixtures; the refusal to start a real gh or security scanner, by the names `tests/support/refused_programs.py` reads from the scanner registry; each test's own data directory, config and gh config, with no way onto the session bus; the pinned GitHub identity; one throwaway kubeconfig for the whole run; the config write guard, a PEP 578 audit hook in the test process in `tests/support/config_write_guard.py`, which refuses a write of a file named like a devops-cli config file, such as `config.yaml` or its copy `config.yaml.bak-<stamp>`, outside the run's temporary directory, also when the code under test catches the refusal; the workspace tripwire, in `tests/support/workspace_tripwire.py`; `tests/support/` with `paths.py`, `waits.py`, the builders in `builders.py`, the `fakes/` package, the pinned identity's `github_identity.py`, and the registration of its modules through `bootstrap.py`, the root conftest's one `pytest_plugins` entry, with the checks that hold a helper's top level and class bodies to statements that bind names, that keep a module from holding `tests.support` or a package under it, and that fail a run on a support fixture or hook its source does not show or on a test module or conftest under `tests/support/`; the check, in the full gate, against reading `__file__` outside `tests/support/` and importing a test module or a conftest; the GitHub session's fake, `GitHubApiFake` in `tests/support/fakes/github.py` behind its `github_api` fixture, which refuses any gh command the rate limiter would run (`run_gh` and the quota refresh), with its contract suite, `tests/test_github_contract.py`, which runs each case through the session over the fake and over GitHub's recorded answers; the security scanners' fake, `ScannerFake` in `tests/support/fakes/scanners.py` behind its `scanner_fake` fixture, a `ToolExecutorFake` that answers Semgrep, Gitleaks, Bandit and osv-scanner with their recorded runs, with its contract suite, `tests/test_scanner_contract.py`, which holds each recording to its adapter's command and the tools lock's version; the OpenSpec fake, `OpenSpecFake` in `tests/support/fakes/openspec.py` behind its `openspec_fake` fixture, which answers `openspec` with the pinned tool's recorded runs over the scenarios of `tests/support/openspec_scenarios.py` (`tests/support/openspec_recording.py` records them again) and fails a command the record lacks, with its contract suite, `tests/test_openspec_contract.py`, which holds the record to the tools lock's version and to the commands the gate starts; the in-memory roadmap store behind the `roadmap_store` fixture, which every test that drives a roadmap command uses, since the roadmap store factory is refused; the in-memory Valkey server behind the `valkey_server` and `valkey_client` fixtures in `tests/support/fakes/valkey.py`, which a `ValkeyClient` reaches through its `connection_pool` parameter, so a test of what the client's own `password`, `db` and decoding arguments send and read binds a loopback listener that records the commands instead, and which has no contract suite yet, since no recorded exchange or local tool stands in for a Valkey server; Hypothesis; syrupy, whose first snapshots are the fail-to-pass replay's could-not-run reports in `tests/__snapshots__/test_fail_to_pass.ambr`; the 90% coverage gate; the structural startup budget; the ast-grep rule against an upper bound on elapsed wall-clock time in `tests/`; and the suppression-ceiling and swallowed-failures ratchets.
- **Review tools**: `ToolExecutor` in `src/devops_cli/security/tool_executor.py` is the seam of the review-tool edge, and `ToolExecutorFake` in `tests/support/fakes/tool_executor.py` is its fake, behind the `tool_executor_fake` fixture. A test scripts a tool with `ToolAnswer` (version, binary digest, exit code, output, `timed_out`) and reads the requests back from `requests`. The fake builds the rest of each `ToolRun` with the `record_tool_run` that the real executor calls.
- **Review tools, programs and canaries**: a request for a tool that the PATH does not name, such as mypy from the interpreter of a `.venv`, names that interpreter as its `program`, and the fake answers it as it answers the tool. Mypy and the canary of each tool take a `tool_executor`, and a review gives them its own. The root conftest answers each canary run of `DirectToolExecutor` with the output in `tests/fixtures/review_canary/recorded_outputs.json`, so a review that gets no executor starts no real tool for its canaries. A test that gives a review the fake scripts the canaries there, or lets them fail.
- **Review tools, records**: the fake names itself `fake` in the record (`FAKE_EXECUTOR`). A review wraps its executor in a `RecordingToolExecutor`. A test that gives the orchestrator the fake reads the records from `orchestrator.tool_executor.runs`, from `profile.tool_runs` and from the Tool Runs table of the report.
- **Review tools, contract suite**: `tests/test_tool_executor_contract.py` runs each shared case over the fake and over the real `SandboxToolExecutor`, with a stand-in for the tool on disk. The real side carries the `bwrap` mark. The cases for `DirectToolExecutor`, the executor of a scanner that gets no other, start git, the one program that the floor allows. The two cases of a record that the direct executor cannot complete also run over `ToolExecutorFake(require_commit=False, require_files=False)`, the fake that stands in for the direct executor and records as it does. The scanners and the review pipeline take a `tool_executor`, and `tests/test_scanner_tool_executor.py` gives them the fake. A scan that gets no executor of its own runs on `DirectToolExecutor`, and `scanner_fake` makes every `DirectToolExecutor` answer through `ScannerFake`, which is such a fake. It puts a stand-in for each scanner that it answers first on PATH, and it patches no `shutil` or `subprocess` name. A request for another tool goes on to the `run` that the fixture replaced, under the floor's refusal of a real scanner. So does a canary run, in a working directory named with `CONST_CANARY_WORKDIR_PREFIX`, which `pin_review_tool_canaries` in the root conftest answers with the recorded canary output.
- **Not yet**: the mirror and the rest of `tests/invariants/`, so most test files still sit flat in `tests/`; a root conftest that holds only the floor, so domain fixtures still sit in it; seams and fakes for most edges, and their contract suites, and the move of the existing fakes into `tests/support/fakes/`; time-machine; and every ratchet but the two above.
- A new test follows each convention whose mechanism exists. Where an edge has no seam yet, the test doubles it through a parameter the code already takes, a shared double already in `tests/`, or the stdlib fallback. Where none of these reaches the edge, the test patches the SDK object itself at the SDK's own module, such as `docker.from_env`, never devops-cli's name for it; the edge's seam replaces that patch with its fake. It adds no patch of devops-cli and no private import; once the ratchets exist, they fail a change that adds either.
- Until the move into the mirror, a new test joins the file that already tests its behaviour, flat or already in its mirror directory such as `tests/ai/review/`, or else goes into a new flat file named after the behaviour.
- The expected outputs under `tests/golden/`, read through `GOLDEN`, predate syrupy and stay until their tests move to snapshots; a new output whose whole text is the contract is a syrupy snapshot.
