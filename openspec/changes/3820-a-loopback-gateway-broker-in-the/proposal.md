# Proposal

## Why

The shell of an implement step cannot reach the two model endpoints of the gateway, so #3820 gives it a loopback broker inside the job process. A key in the shell would undo #2667, because the shell runs as the same user as the job process, and a Caddy sidecar cannot keep it either, since `execve` sets the dumpable flag again. The job process already holds the key and is not dumpable, so the broker runs there and gives each step a token that dies with the step.

## What Changes

- Add `src/devops_cli/roadmap/implement/implement_broker.py`: a FastAPI app on `127.0.0.1` and an ephemeral port inside the job process, a per-step bearer token, and one upstream call per allowed pair, built with `http_client` at the level of `configured_level`, so the connect is vetted and the AI key of the job process goes upstream.
- The broker forwards only the exact pairs `POST /chat/completions` and `POST /embeddings` under the path prefix of `ai.gateway_url`; every other method or path is refused and reaches no gateway.
- `start_step_broker` refuses a host that is not a loopback address with the roadmap implement error that names it, and `stop_step_broker` closes the server, its client and the token of the step.
- `shell_environment` gives the shell `DEVOPS_CLI_BROKER_URL` and `DEVOPS_CLI_BROKER_TOKEN` of the live broker; the environment and the arguments of the shell hold no AI key.
- `run_step` holds the budget of the step in a local, starts the broker before the first attempt and stops it first in its `finally`, so the token dies with the step, also when the step stops or raises.
- A forwarded answer adds its new tokens to the step budget and its requests and tokens to the tier record under the tier that served the call.
- A step whose `ai.provider` is not `gateway`, or that has no AI key, runs no broker and gives the shell neither variable.
- `docs/CLUSTER.md` states the broker, its two variables, its two endpoints and its accounting; the delta also adds the two variables to the exception list of the requirement `A runner process cannot be read by its own shell` of `roadmap-implement-job/runner-job`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-step/shell`: The step runs a loopback broker for its shell, The broker forwards only the allowed requests, The shell of a step gets the broker address and the step token
- `roadmap-implement-step/budgets`: A shell call through the broker counts as a model call of the step
- `roadmap-implement-job/runner-job`: A runner process cannot be read by its own shell

## Impact

- Code: `src/devops_cli/roadmap/implement/implement_broker.py`, `src/devops_cli/roadmap/implement/implement_step.py`
- Documents: `docs/CLUSTER.md`
- Tests: `tests/roadmap/implement/test_roadmap_implement_broker.py`, `tests/roadmap/implement/test_roadmap_implement_step.py`, `tests/roadmap/implement/test_roadmap_implement_job.py`, `tests/roadmap/implement/test_roadmap_implement_tier_move.py`

## Feasibility

- The probes confirm the cited paths, word for word: "The path `src/devops_cli/roadmap/implement/implement_shell_policy.py` is a file of the staging commit." and "The path `CONTEXT.md` is a file of the staging commit." They also say what they did not check: "Not probed, the bound of 10 commands is reached: `it.gateway`, `They.per`, `execve`, `fastapi`, `uvicorn`, `httpx2`", so this run read the pins itself: `search_code` for `fastapi==` returned `pyproject.toml:37:"fastapi==0.162.7",`, `search_code` for `uvicorn==` returned `pyproject.toml:38:"uvicorn==0.54.0",`, and `search_code` for `httpx2==` returned `pyproject.toml:18:"httpx2==2.16.2",`.
- The fault of the previous reply is fixed at the place that named the class. `search_code` for `class RoadmapImplementError` returned one hit in `src/devops_cli/exceptions/roadmap.py`, whose line 61 reads `class RoadmapImplementError(DevOpsCLIError):`, and `read_file` of lines 55 to 70 of that file showed the same class, its docstring and `src/devops_cli/exceptions/roadmap.py:67:error_code = "ROADMAP_IMPLEMENT_REFUSED"`. The design decision now names no class, and the group that raises it cites the symbol as `src/devops_cli/exceptions/roadmap.py:class RoadmapImplementError`.
- `list_files` of `src/devops_cli/roadmap/implement` returned no `implement_broker.py`, and `list_files` of `tests/roadmap/implement` returned no `test_roadmap_implement_broker.py`, so group 1 creates both. That listing returned `test_roadmap_implement_step.py`, `test_roadmap_implement_job.py` and `test_roadmap_implement_tier_move.py`, which groups 2, 3 and 4 change.
- `search_code` for `shell_environment` returned `src/devops_cli/roadmap/implement/implement_step.py:557:def shell_environment(home: Path) -> dict[str, str]:` and `src/devops_cli/roadmap/implement/implement_step.py:604:env=shell_environment(home),`, and in the tests `tests/roadmap/implement/test_roadmap_implement_step.py:579:env = shell_environment(tmp_path / "home")`, plus four files under `openspec/changes/archive/`; group 2 changes both files outside the archive.
- `read_file` of lines 540 to 580 of `src/devops_cli/roadmap/implement/implement_step.py` showed `src/devops_cli/roadmap/implement/implement_step.py:554:_PASSED_VARIABLES = ("UV_PYTHON", "PYTEST_XDIST_AUTO_NUM_WORKERS")` and the six variables that `shell_environment` builds, so the two broker variables join that dict and the tuple stays as it is.
- `read_file` of lines 570 to 645 of `tests/roadmap/implement/test_roadmap_implement_step.py` showed `tests/roadmap/implement/test_roadmap_implement_step.py:571:def test_the_shell_runs_with_a_scratch_home_and_the_cache_of_uv(`, which compares the whole environment with a fixed dict; it keeps passing because no broker is live in that test.
- `file_symbols` of `src/devops_cli/roadmap/implement/implement_step.py` showed `def run_step` at line 2348, `class TierSpend` at line 478, `def plus` at line 490, `def shell_environment` at line 557 and `def _tier_for_attempt` at line 654. `read_file` of lines 2430 to 2460 showed `src/devops_cli/roadmap/implement/implement_step.py:2447:limits=StepBudget(spend, progress=log.progress, cap=token_cap),` and `src/devops_cli/roadmap/implement/implement_step.py:2457:end_step(source, inputs.group.title)` after the `finally`, so group 3 holds the budget in a local, starts the broker before the attempt and stops it first in that `finally`.
- `read_file` of lines 2200 to 2210 showed `src/devops_cli/roadmap/implement/implement_step.py:2204:tier, attempt = _tier_for_attempt(tiers, attempt, tier_health)`, the one place that picks the tier of an attempt, so group 4 marks that tier on the live broker there and leaves `_tier_for_attempt` pure.
- `file_symbols` of `src/devops_cli/roadmap/implement/implement_limits.py` showed `src/devops_cli/roadmap/implement/implement_limits.py:215:def add(self, tokens: int) -> None:`, which takes the new tokens of a forwarded answer.
- `file_symbols` of `src/devops_cli/http/entry.py` showed `def http_client` at line 55 and `def install_transport` at line 249, and `file_symbols` of `src/devops_cli/http/egress.py` showed `src/devops_cli/http/egress.py:67:def configured_level(ai_config: AIConfig | None = None) -> EgressLevel:`, so the broker builds its upstream client there and a test replaces that transport.
- `search_code` for `none of the variables of the job` returned `docs/CLUSTER.md:76:The shell of a step has none of the variables of the job, except the uv paths and the worker bound of the test runner.`, the bullet that group 5 edits.
- `read_spec` of `roadmap-implement-job/runner-job` returned the base requirement `A runner process cannot be read by its own shell`, whose text ends with the exception list `UV_CACHE_DIR`, `UV_PYTHON` and `PYTEST_XDIST_AUTO_NUM_WORKERS`; the delta modifies that requirement and adds the two broker variables to the list.
- `read_spec` of `roadmap-implement-step/shell` returned its purpose and its requirement names, and `read_spec` of `roadmap-implement-step/budgets` returned the same; no name of this delta is one of them, so the delta adds new requirements there and modifies none of them.
- `search_code` for `start_step_broker`, for `plus_shell`, for `StepBroker`, for `ALLOWED_REQUESTS` and for `DEVOPS_CLI_BROKER` returned no match, so every name that groups 1 and 4 add is new.
- `read_issue` of #3563 showed it closed (not_planned), with "No merged pull request closed it." and the comment "the split of that comment is now filed: - #3820: a loopback gateway broker in the job process (item A). - #3823: the runner pod reads Qdrant with a scoped key (item B). - #3827: `devops review` runs in the runner shell (item C).", so no merged change did this work and this item is the split that carries item A.
- `find_issues` for `loopback gateway broker` returned `#3820 open feat(roadmap): a loopback gateway broker in the job process` and `#5506 open feat(roadmap): the model container of a unit holds no credential`; #5506 consumes the broker of this item, so it comes after and blocks nothing here, and `dependencies` stays empty.
- Precondition of `http_client` of `src/devops_cli/http/entry.py:def http_client`: a network to the gateway; each test replaces the transport through the `web` fixture, so no test reaches a network.
- Precondition of `apply_implement` of `src/devops_cli/roadmap/implement/implement_run.py:def apply_implement`: a checkout of the repository, a client of the store and a model client; the end-to-end test of group 3 gives a `job_world` checkout, an in-memory store and a scripted model.
- Precondition of `run_step` of `src/devops_cli/roadmap/implement/implement_step.py:def run_step`: a checkout, a store client and a model; group 3's test gives them through `job_world`, and group 1's test needs only a loopback socket in the test process.
- Precondition of the AI key: a client of the OS keyring or the environment; only the job process reads it, and a test sets it in the environment of the process.
- The plan introduces no program: `uv run devops ci test` and `uv run devops ci docs` run the runner tools `uv` and `devops`, which the image holds; a failing test gives the failure class `test`, and the pod runs with `runAsNonRoot`, `readOnlyRootFilesystem: true`, `allowPrivilegeEscalation: false`, `capabilities.drop: ALL` and `seccompProfile: RuntimeDefault`.
- The first checks against the real system: `uv run devops ci test tests/roadmap/implement/test_roadmap_implement_broker.py`, then `uv run devops ci test tests/roadmap/implement/test_roadmap_implement_step.py`, then `uv run devops ci test tests/roadmap/implement/test_roadmap_implement_job.py`, then `uv run devops ci test tests/roadmap/implement/test_roadmap_implement_tier_move.py`, then `uv run devops ci docs`.

## Existing Tool Considered

fastapi/fastapi (MIT, in use) is open and maintained, and the staged `pyproject.toml` pins `fastapi==0.162.7`, `uvicorn==0.54.0` and `httpx2==2.16.2`; they run the loopback server, and `http_client` of `src/devops_cli/http/entry.py` builds the upstream client. The token, the allowlist and the accounting are the only new code: about 8k tokens to build, keep and fix, and 2 hours, because the libraries carry the HTTP work.

## Dependencies

None.
