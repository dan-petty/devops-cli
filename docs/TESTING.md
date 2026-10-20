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
A test whose subject is a committed file of this repository (the source tree, docs, task files, workflows, manifests or dashboards) rather than the behaviour of devops-cli.
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
- **Faked edges**: every program except git, bwrap and kubectl's offline renderers (gh, the rest of kubectl, helm, minikube, the docker and podman CLIs, the scanners, and `uv run devops` calling itself), with `shutil.which` part of the process fake; all network, meaning HTTP on any client stack, raw sockets and DNS; GitHub's API, through the GitHub session or the PyGithub REST client; model and embedding providers; the Kubernetes API; the Docker engine; Valkey; Qdrant; outbound MCP servers; durable backends; OTLP export; the keyring and D-Bus.
- **Real**: the filesystem under `tmp_path`; environment and config, through the hermetic floor and the `config` fixture *(target)*; git in temporary repositories; kubectl's offline renderers, `kubectl kustomize` and `kubectl patch --local`, which read only files and reach no cluster; bwrap in live tests; in-process servers, such as FastAPI's `TestClient` and loopback servers; randomness; host identity; and stdin, through `CliRunner(input=...)`.
- No test starts a real gh, which would act as the developer's own login: a gh command a test reaches goes to a fake, and the floor fails a test that starts gh.
- No test starts a real security scanner either: a scanner fetches rule packs and advisories from a child process the network block does not see. The floor refuses gh and the binary of every scanner the security scanner registry holds, names `tests/support/refused_programs.py` reads from the registry when the run starts, so a scanner added there is refused with no list to edit. The refusal sits at `subprocess.Popen`, beneath every seam, and fails the test with `pytest.fail`, which no `except Exception` in the code under test hides. A test whose code starts a scanner asks for `scanner_fake`, which answers with the scanner's run recorded from the real tool.
- No test starts sudo, which changes the host, or uv installing or syncing from PyPI, and the floor refuses both *(target)*. The gate's own `uv audit`, `uv tree --outdated` and `uv check` are its intended network checks, run by `devops ci`, never by a test.
- Each edge has one seam in `src/devops_cli`: a Protocol, plus the one place that supplies the real implementation *(target for most edges)*. The clock's seam is the sleep and clock parameters the libraries take, with no Protocol, as [Clock](#clock) describes. A test installs the edge's fake through the seam's fixture, or through a constructor or parameter the domain code already takes.
- Each edge has one fake, in `tests/support/fakes/<edge>.py`, shared by every test that reaches the edge. A test does not build its own double of an edge.
- Every fake has a contract suite, run against the fake and against the real implementation over recorded responses or a real local tool, never a live service. A fake without a contract suite does not merge.
- Patching a stdlib or SDK object itself, such as `subprocess.run` or `time.sleep`, is a fallback for stdlib edges only.
- No test patches a devops-cli module, class, function or attribute, and no test imports a private name (one that starts with `_`) from `devops_cli`. A test reaches private code through the public interface that uses it.
- Product code holds nothing for tests: no `unittest.mock`, no `PYTEST_CURRENT_TEST` check, no check for a mock's attributes, and no module shaped so that a test can patch it. Fakes, and in-memory implementations that production does not use, live in `tests/support/` and never ship in the wheel.

### Layout

- `tests/` mirrors the package tree of `src/devops_cli` at full depth *(target)*: the tests of `src/devops_cli/ai/review/` sit in `tests/ai/review/`. Each package directory has its own `conftest.py` for that package's fixtures.
- A package is tested through its public interface, in one file per behaviour, named after the behaviour, such as `tests/roadmap/test_descoping.py` *(target)*; not in one file per source module. A test of behaviour that crosses packages goes to the package that owns the behaviour.
- A file is never named after the work that produced it: a review session, an issue, a pull request, a batch or a hardening pass. A regression test joins the file of the behaviour it pins.
- `tests/invariants/` *(target)* is the only place for test files outside the mirror. It holds the invariant tests, one file per subject: `test_source_tree.py`, `test_agents_md.py`, `test_task_files.py`, `test_workflows.py`, `test_k8s_manifests.py` and `test_grafana_dashboards.py`. A new invariant test goes into its subject's file, created if absent, never into a parallel file.
- `tests/support/` holds what tests share, and no test module or conftest lives in it, which the registration enforces: the fakes in `fakes/<edge>.py`, the builders in `builders.py`, and shared fixtures. Every submodule and subpackage under it is registered as a plugin, so a fixture added there needs no conftest edit: the root conftest's one `pytest_plugins` entry names `tests.support.bootstrap`, which isolates HOME and then registers the rest, so a support module that imports devops-cli binds its paths under the isolated HOME. The root conftest marks `tests.support` for assertion rewriting first and imports it only inside functions, and `PytestAssertRewriteWarning` is an error, so a support module imported too early fails the run. A support module defines no `pytest_*` name that is not a hook, and defines each fixture it registers with `pytest.fixture` rather than importing another module's or handing one out by a module-level `__getattr__`: the registration fails a run whose support module holds a fixture or hook its source does not show. An invariant holds the top level and the class bodies of every helper module under `tests/` to docstrings, imports at the top level, defs, classes, assignments to names alone and `if TYPE_CHECKING:` blocks with no `else`; the values bound to names, decorators, default arguments, base classes and metaclasses still run on import unchecked. A module imports from a support module with `from tests.support[.x] import ...`, and no module but `bootstrap` holds `tests.support` or a package under it, which another invariant enforces, so none reads a support module it does not import.
- A test finds the repository root and its test data through `tests.support.paths`: `REPO_ROOT`, `TESTS_ROOT`, `FIXTURES` (`tests/fixtures/`) and `GOLDEN` (`tests/golden/`). It never builds a path from its own `__file__`, so it reads the same paths at any depth.
- A test file imports what it shares from `tests/support/`, never from another test file or from a conftest. One check over every Python file under `tests/` but `tests/fixtures/` fails the full gate on a module that reads `__file__` outside `tests/support/` or imports a test module or a conftest, naming each as `path:line`: an imported module under `tests`, or a top-level one, is a test module when pytest collects its file by the `python_files` patterns; `from X import n` imports the module `X.n` when `X` is a package or `X/n.py` exists; and a relative import is resolved against the importing module's package, one past the top-level package being reported too. It lives alone in `tests/test_test_module_independence.py`, which no change to a source or helper module selects, as the next section says.
- The root `tests/conftest.py` holds only the hermetic floor *(target)*. Domain fixtures live in their package's conftest or beside their fake.

### Names and assertions

- A test is named after the behaviour it checks, in [CONTEXT.md](../CONTEXT.md) glossary terms: `test_stalled_item_is_treated_as_not_started`. The name never names a helper, a private function or a double, and it uses the glossary term, never a word the glossary lists under _Avoid_.
- An assertion compares whole values: `assert result == expected` against a complete expected model, or `assert fake.requests == [...]` for what an edge was asked.
- A test of an error path checks the `DevOpsCLIError` subclass raised, with its exit code and machine-readable error code.
- Tuple equality is only for picking fields out of an object whose other fields are noise, such as generated ids or timestamps.
- Consecutive asserts are fine. Ruff's C901 does not count them, so they do not raise a test's complexity.

### CLI tests

- A CLI test invokes a command through the shared `cli` fixture *(target)*, not through a `CliRunner` it builds itself.
- It checks only what the command layer owns: argument parsing, wiring, output and exit code. Every CLI test sits in `tests/commands/` *(target: a few do today)* and reaches edges only through its fakes.
- A domain rule is tested once, through its domain package. Logic behind a private helper in `commands/` moves into its domain package behind a public function and is tested there, and the command becomes a thin adapter. Until it moves, it is tested through the CLI with edge fakes.

### Config

- A test sets configuration through the `config` fixture *(target)*. The fixture writes the overrides into the test's own `config.yaml`, the file `DEVOPS_CLI_CONFIG` names, and resets the settings cache.
- No test patches `load_settings` or `CONFIG_PATH`.

### Test data

- A test builds a domain object with a builder: one per glossary term, named after it (`make_finding`, `make_verdict`, `make_item`, `make_release`, `make_candidate`, `make_changelog_fragment`), in `tests/support/builders.py`. A builder is a plain function that builds a valid object through the real constructor or parser, with its validation, from valid defaults, and takes keyword-only overrides; a model's builder refuses a key that is no field of the model with `TypeError` naming it, so a typo or an alias fails rather than being dropped.
- An output whose whole text is the contract, such as a command's output, a rendered manifest or a prompt, is checked against a snapshot that syrupy stores. Any other expected value is a literal written in the test. A Pydantic model is snapshotted through `model_dump()` or syrupy's Amber Pydantic plugin.
- A snapshot is regenerated, never edited by hand, with `uv run pytest <test-file> --snapshot-update --snapshot-file-lock`, and the commit says why it changed. The file lock is required: without it, an update under xdist can lose entries from a shared `.ambr` file ([syrupy issue 1237](https://github.com/syrupy-project/syrupy/issues/1237)).

### Property tests

- State machines, such as the roadmap lifecycle and a release's cut and ship, and pure functions over open-ended input, such as parsers, policy evaluation and redaction, are tested with Hypothesis properties.
- Everything else is tested with examples.

### Clock

- Wall-clock reads are faked with time-machine *(target)*. freezegun is not used: it is unmaintained, and its frozen monotonic clock hangs asyncio and tenacity.
- Waiting goes through the sleep and clock parameters the libraries already take, such as tenacity's `sleep=` and the `sleep` of pydantic-ai's retry configuration, and one place in `src/devops_cli` supplies the real ones *(target)*. A direct `time.sleep` is patched at the stdlib, the fallback for stdlib edges. devops-cli has no Clock type of its own.
- No test asserts on elapsed wall-clock time, which a loaded machine stretches. A budget counts something the run decides: the startup budget in `tests/test_cli_startup_imports.py` counts the modules that `--version`, the root `--help` and a few commands' `--help` import, and fails on any heavy module that any command group's `--help` imports, never on seconds.

### Waiting for another thread

- A test that waits for something another thread or process does waits with `THREAD_HANDOFF_BOUND_SECONDS` from `tests/support/waits.py`, through `Event.wait`, `Queue.get`, `Thread.join`, `Barrier(timeout=...)` or `wait_until`, never with a deadline of its own. The wait returns as soon as its event happens, so only a failing test waits the bound out; a 1 or 2 s deadline failed correct code while a loaded host kept a ready thread waiting for a CPU.
- Anything a test relies on to stay alive or blocked, such as a sleeping child process or a job held until the test releases it, outlives the bound of every wait that observes it, or records whether the test ended it and asserts that it did. A hold on its observer's bound runs out inside the observer's window, and the test passes with the bug it checks for.
- A wait that checks that nothing happens keeps a short window of its own, opened only after a bounded, asserted wait shows the competing thread has reached the point where the event would happen. A comment at the window says so.
- Every test runs under pytest-timeout's per-test bound, `timeout` in `[tool.pytest.ini_options]`, with `timeout_method = "signal"`, so a test that hangs fails in its own process, naming itself, and the run and its xdist worker carry on. The bound is a hang bound, far above the slowest test on a loaded host and above every wait's bound; a test that needs longer says so with `@pytest.mark.timeout(<seconds>)`.

### Which tests a narrowed run selects

- `devops ci test <paths>` runs only the tests a change reaches, and so does `devops test run --changed`, over the files changed since the branch left `main`, committed or not. A test module is reached when it is named for a changed module, at any depth, or imports it. A test module that only sits in the directory mirroring the module's package is not reached.
- Given no `-n`, a narrowed `devops ci test` runs serially for up to `DEFAULT_CI_TEST_SERIAL_MAX_FILES` test modules, where starting xdist workers costs more than it saves, and on `DEFAULT_CI_TEST_NARROWED_WORKERS` workers above that; the full suite, and the fallback to it, run on `addopts`' `-n logical`. It runs pytest in a session of its own, so a timeout, Ctrl-C, SIGTERM or SIGHUP stops pytest and its workers with `uv`: a timeout with SIGTERM, a signal by first forwarding the SIGINT a terminal would have sent, so pytest runs its teardown, then SIGTERM and SIGKILL, which a second signal brings forward and cannot skip. A test that drives `devops ci test` doubles `asyncio.create_subprocess_exec` with `record_spawns` from `tests/support/session_spawns.py`, and asks for `refuse_nested_test_runs`, which fails any real `uv` or pytest it would start.
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

- Every test runs inside the hermetic floor, which the root conftest supplies: the network block; the refusal to start a real gh or security scanner; the test's own data directory, config and gh config, with no way onto the session bus; a pinned GitHub identity, so a gh or git child gets a placeholder token, never the developer's login; a throwaway kubeconfig for the run; and the workspace tripwire, which fails the run when a test writes to the workspace's `config.yaml` or to a tracked file.
- The floor fails a test that reaches a faked edge without its fake, with an error naming the edge *(target)*.
- After every test, the floor calls the public reset of every process-wide cache and singleton, and an invariant test fails a module-level cache or `global` in `src/devops_cli` that has no reset there *(target)*.
- Telemetry export is off unless a test opts in with the OTLP fake *(target)*.
- Ratchets hold each thing being retired to a ceiling that may only go down: `test_c901_suppressions_stay_under_the_ceiling` in `tests/test_architectural_invariants.py` holds the `# noqa: C901` markers, and `tests/test_swallowed_failures_ratchet.py` the swallowed failures. Patches aimed at devops-cli, imports of its private names, test accommodations in product code (`unittest.mock`, `PYTEST_CURRENT_TEST` and mock-attribute checks) and test files outside the layout get ratchets of their own *(target)*. A change that passes a ceiling is fixed, and the ceiling is never raised; a ratchet at zero becomes a ban.

### Until the migration ends

The suite moves to these conventions package by package ([ADR 0007](adr/0007-tests-double-only-process-edges.md)). Until the move is done:

- **Exists today**: the network block; the refusal to start a real gh or security scanner, by the names `tests/support/refused_programs.py` reads from the scanner registry; each test's own data directory, config and gh config, with no way onto the session bus; the pinned GitHub identity; one throwaway kubeconfig for the whole run; the workspace tripwire, in `tests/support/workspace_tripwire.py`; `tests/support/` with `paths.py`, `waits.py`, the builders in `builders.py`, the `fakes/` package, the pinned identity's `github_identity.py`, and the registration of its modules through `bootstrap.py`, the root conftest's one `pytest_plugins` entry, with the checks that hold a helper's top level and class bodies to statements that bind names, that keep a module from holding `tests.support` or a package under it, and that fail a run on a support fixture or hook its source does not show or on a test module or conftest under `tests/support/`; the check, in the full gate, against reading `__file__` outside `tests/support/` and importing a test module or a conftest; the GitHub session's fake, `GitHubApiFake` in `tests/support/fakes/github.py` behind its `github_api` fixture, which refuses any gh command the rate limiter would run (`run_gh` and the quota refresh), with its contract suite, `tests/test_github_contract.py`, which runs each case through the session over the fake and over GitHub's recorded answers; the security scanners' fake, `ScannerFake` in `tests/support/fakes/scanners.py` behind its `scanner_fake` fixture, which answers Semgrep, Gitleaks and Bandit with their recorded runs, with its contract suite, `tests/test_scanner_contract.py`, which holds each recording to its adapter's command and the tools lock's version; the in-memory roadmap store behind the `roadmap_store` fixture, which every test that drives a roadmap command uses, since the roadmap store factory is refused; Hypothesis; syrupy, whose first snapshots are the fail-to-pass replay's could-not-run reports in `tests/__snapshots__/test_fail_to_pass.ambr`; the 90% coverage gate; the structural startup budget; and the C901 and swallowed-failures ratchets.
- **Not yet**: the mirror and `tests/invariants/`, so most test files still sit flat in `tests/`; a root conftest that holds only the floor, so domain fixtures still sit in it; seams and fakes for most edges, and their contract suites, and the move of the existing fakes into `tests/support/fakes/`; the `cli` and `config` fixtures; time-machine; the floor's default deny, its refusal of sudo and of uv installing or syncing from PyPI, its reset of process-wide state, and telemetry export off by default; and every ratchet but the two above.
- A new test follows each convention whose mechanism exists. Where an edge has no seam yet, the test doubles it through a parameter the code already takes, a shared double already in `tests/`, or the stdlib fallback. Where none of these reaches the edge, the test patches the SDK object itself at the SDK's own module, such as `docker.from_env`, never devops-cli's name for it; the edge's seam replaces that patch with its fake. It adds no patch of devops-cli and no private import; once the ratchets exist, they fail a change that adds either.
- Until the move into the mirror, a new test joins the file that already tests its behaviour, flat or already in its mirror directory such as `tests/ai/review/`, or else goes into a new flat file named after the behaviour.
- The expected outputs under `tests/golden/`, read through `GOLDEN`, predate syrupy and stay until their tests move to snapshots; a new output whose whole text is the contract is a syrupy snapshot.
- Until the `config` fixture exists, a test writes its overrides into the `config.yaml` that the autouse `isolate_devops_cli_config` fixture yields, then calls `reset_settings_cache()` from `devops_cli.config.settings`.
