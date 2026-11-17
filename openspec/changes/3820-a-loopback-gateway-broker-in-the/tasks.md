# Tasks

## 1. Add the loopback broker of a step

Kind: behavior. Reads: `src/devops_cli/server/app.py`, `src/devops_cli/http/entry.py`, `src/devops_cli/http/egress.py`, `src/devops_cli/roadmap/implement/implement_limits.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/exceptions/roadmap.py`. Changes: `src/devops_cli/roadmap/implement/implement_broker.py` (new), `tests/roadmap/implement/test_roadmap_implement_broker.py` (new).
Adds: `ALLOWED_REQUESTS`, `BrokerSpend`, `StepBroker`, `broker_app`, `live_broker`, `loopback_broker_url`, `start_step_broker`, `stop_step_broker`

- [x] 1.1 `tests/roadmap/implement/test_roadmap_implement_broker.py::test_an_allowed_request_reaches_the_recorded_gateway` first: a POST to /chat/completions with the step token reaches the gateway that the `web` fixture records, through `start_step_broker`; then a test for another path, another method, another token, the token after `stop_step_broker`, a host that is not loopback, and an answer that holds no AI key
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_broker.py` fails on the base
- [x] 1.2 Create `src/devops_cli/roadmap/implement/implement_broker.py`. `ALLOWED_REQUESTS` holds the two pairs POST /chat/completions and POST /embeddings. `loopback_broker_url` parses the host with `ipaddress.ip_address` and refuses a host that is not loopback. `broker_app` builds the FastAPI app in the shape of `src/devops_cli/server/app.py`, with one route per allowed pair under the path prefix of the gateway URL, a bearer check with `secrets.compare_digest`, and an upstream call that adds the AI key. The upstream call builds its client with `http_client` of `src/devops_cli/http/entry.py` at the level of `configured_level` of `src/devops_cli/http/egress.py`; the module calls no `httpx2.Client` and no `httpx2.post`, so the rule `net-raw-http-client` passes and the connect is vetted as the agent's is. `StepBroker` holds the token, that client, the budget of `src/devops_cli/roadmap/implement/implement_limits.py`, the current tier, and a `BrokerSpend` for each tier. `start_step_broker` reads `ai.gateway_url` and the AI key of `src/devops_cli/config/settings.py`, returns no broker when `ai.provider` is not `gateway` or the key is absent, runs uvicorn in a thread on an ephemeral loopback port, and registers the broker as the live one; `stop_step_broker` closes the server, the client and the token, and clears the live broker. A start with a host that is not loopback raises `src/devops_cli/exceptions/roadmap.py:class RoadmapImplementError` and listens on no port. Write the test first: the `web` fixture records the forwarded gateway request, and the test posts to the loopback address
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_broker.py` passes

## 2. Give the shell of a step the broker address and its token

Kind: behavior. Reads: `src/devops_cli/roadmap/implement/implement_step.py`, `src/devops_cli/roadmap/implement/implement_broker.py`, `src/devops_cli/config/settings.py`, `tests/roadmap/implement/test_roadmap_implement_step.py`. Changes: `src/devops_cli/roadmap/implement/implement_step.py`, `tests/roadmap/implement/test_roadmap_implement_step.py`.

- [x] 2.1 `tests/roadmap/implement/test_roadmap_implement_step.py::test_the_shell_environment_of_a_step_holds_the_broker_and_no_ai_key` first: with a live broker and the AI key in the environment of the process, the environment that `shell_environment` gives the shell holds the broker address and the step token and no value of the key, and the arguments of the shell call hold no key; then `tests/roadmap/implement/test_roadmap_implement_step.py::test_a_step_with_no_gateway_gets_no_broker`, which asserts that neither variable is set
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_step.py` fails on the base
- [x] 2.2 In `src/devops_cli/roadmap/implement/implement_step.py`, `shell_environment` reads the live broker of `src/devops_cli/roadmap/implement/implement_broker.py` and adds `DEVOPS_CLI_BROKER_URL` and `DEVOPS_CLI_BROKER_TOKEN` when one is live; the environment still holds no AI key and the tuple `_PASSED_VARIABLES` stays as it is. With no live broker the function returns the same dict as today, so `test_the_shell_runs_with_a_scratch_home_and_the_cache_of_uv` keeps its exact comparison. The module `tests/roadmap/implement/test_roadmap_implement_step.py` holds the existing tests of `shell_environment` and gains the two new tests
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_step.py` passes

## 3. Run the broker for the length of a step

Kind: behavior. Reads: `src/devops_cli/roadmap/implement/implement_step.py`, `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/roadmap/implement/implement_broker.py`, `src/devops_cli/config/settings.py`, `tests/roadmap/implement/test_roadmap_implement_job.py`, `tests/roadmap/implement/test_roadmap_implement_command.py`. Changes: `src/devops_cli/roadmap/implement/implement_step.py`, `tests/roadmap/implement/test_roadmap_implement_job.py`.

- [x] 3.1 `tests/roadmap/implement/test_roadmap_implement_job.py::test_apply_implement_gives_a_step_shell_the_broker_variables_and_no_ai_key` first: `job_world` runs a recorded step through `apply_implement` of `src/devops_cli/roadmap/implement/implement_run.py`, and the test asserts that the AI key value is in neither the environment nor the command of the shell, that the broker variables are there, and that a request with the token is refused after the step ends; then `tests/roadmap/implement/test_roadmap_implement_job.py::test_a_stopped_step_still_ends_its_broker`
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_job.py` fails on the base
- [x] 3.2 In `src/devops_cli/roadmap/implement/implement_step.py`, `run_step` holds the `StepBudget` that it passes to `_attempt` in a local, calls `start_step_broker` with it before the first attempt, and calls `stop_step_broker` first in the `finally`, before `end_step`, so the token dies with the step, also when the step stops or raises. `start_step_broker` reads the settings and returns no broker for a provider that is not `gateway` or for an absent AI key, so `run_step` adds no settings read. The end-to-end tests go in `tests/roadmap/implement/test_roadmap_implement_job.py`, the module of the job-level tests that take `job_world`
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_job.py` passes

## 4. Count a shell call in the budget and the tier record

Kind: behavior. Reads: `src/devops_cli/roadmap/implement/implement_step.py`, `src/devops_cli/roadmap/implement/implement_broker.py`, `tests/roadmap/implement/test_roadmap_implement_tier_move.py`. Changes: `src/devops_cli/roadmap/implement/implement_step.py`, `tests/roadmap/implement/test_roadmap_implement_tier_move.py`.
Adds: `plus_shell`

- [x] 4.1 `tests/roadmap/implement/test_roadmap_implement_tier_move.py::test_a_shell_call_lands_on_the_tier_of_its_attempt` first: a two-tier ladder and a broker whose gateway the `web` fixture records, asserting the new tokens in the step budget and the same requests and tokens in the `StepOutcome` `tier_spend` of each tier
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_tier_move.py` fails on the base
- [x] 4.2 In `src/devops_cli/roadmap/implement/implement_step.py`, `_attempt` sets the tier that `_tier_for_attempt` returned on the live broker of `src/devops_cli/roadmap/implement/implement_broker.py`, so a shell call of an attempt is recorded under the tier that served it, and `_tier_for_attempt` stays a pure function. `TierSpend.plus_shell` adds the requests, input tokens, cache-read tokens and output tokens of a `BrokerSpend`. `run_step` merges the spend of the broker into the outcome with `model_copy`: each tier of `tier_spend` gets its counts, and the totals of the outcome get the same counts. A shell call on an empty tier adds to the totals only, as the model spend of that tier does
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_tier_move.py` passes

## 5. Document the broker of a step

Kind: other. Reads: `docs/CLUSTER.md`, `src/devops_cli/roadmap/implement/implement_broker.py`. Changes: `docs/CLUSTER.md`.

- [ ] 5.1 In the **Guarantees.** bullet of `docs/CLUSTER.md`, add the broker address and the step token to the list of values that the shell of a step gets, and state the broker: the job process runs it on the loopback interface for the step, it mints both variables for the step, it forwards only POST /chat/completions and POST /embeddings through the one HTTP client entry point, the AI key stays in the job process, the token dies when the step ends, and a shell call counts in the step budget and in the tier record
  - Verification: `$ uv run devops ci docs` passes
- [ ] 5.2 Edit `docs/CLUSTER.md`: the broker of a step, its two variables, its two endpoints and its accounting
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 1: A test: a request with the step token to an allowed method and path reaches the recorded gateway.
- Group 1: A test: a request to any other path or method, or with another token, is refused.
- Group 1: A test: the token stops working when the step ends.
- Group 2: A test: the environment and arguments of the shell hold no gateway key.
- Group 1: The change names the allowed paths and says how a shell call counts against the step budget and tier accounting. `/chat/completions` and `/embeddings` are the same endpoints as the model of the agent, so the decision is part of this item.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
