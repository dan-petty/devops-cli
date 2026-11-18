# Design

## Decisions

- **Build the upstream client of the broker with `http_client(configured_level(ai_config))` of `src/devops_cli/http/entry.py`, and call no `httpx2.Client` or `httpx2.post` in the module.**: The rule `net-raw-http-client` of `.ast-grep/rules/` makes a raw client an error under `src/**`, and the entry point is also the transport that the `web` fixture replaces, so a test records the forwarded gateway request.
- **Allow only the exact pairs POST /chat/completions and POST /embeddings, under the path prefix of `ai.gateway_url`, in one constant `ALLOWED_REQUESTS`.**: The issue names these two endpoints, and they are the endpoints of the model of the agent and of `devops ai rag-query`; one constant holds them.
- **Count a shell call as a model call of the agent: the step budget takes its new tokens through `def add` of `src/devops_cli/roadmap/implement/implement_limits.py:class StepBudget`, and `run_step` puts its requests and tokens in the `tier_spend` of `src/devops_cli/roadmap/implement/implement_step.py:class TierSpend` under the tier of the attempt.**: The endpoints are the same, so one budget and one tier record avoid a split cost and hidden spend.
- **Give the shell `DEVOPS_CLI_BROKER_URL` and `DEVOPS_CLI_BROKER_TOKEN` and nothing else, and keep the AI key in the job process.**: The job mints the two values for the step, so they are no variables of the job, and neither carries the key.
- **Modify the requirement `A runner process cannot be read by its own shell` of `roadmap-implement-job/runner-job` to add the two broker variables to its exception list.**: The living spec then states the values that the shell gets, so no requirement contradicts the change after the archive.
- **Create one random token per step in job-process memory, and drop it in `stop_step_broker`.**: The token dies with the step and leaves no file and no process that a later step can read.
- **Run the broker with FastAPI and uvicorn on `127.0.0.1` and an ephemeral port.**: The project already depends on the libraries, and only a process of the pod reaches a loopback port.
- **Refuse a host that is not a loopback address in `start_step_broker` with the roadmap implement error of the job, which names the address, and bind no port then.**: A broker on a pod address is reachable by other pods, and its port would need a fixed allocation.
- **Let `shell_environment` read the live broker of the broker module, and let `run_step` start and stop it, so no other function of the step takes a new parameter.**: One place starts the broker and one ends it, every existing caller keeps its call, and the shell environment of a step with no broker stays as it is.
- **Let `start_step_broker` read the settings and return no broker when `ai.provider` is not `gateway` or the AI key is absent.**: `run_step` then holds no second settings read, and the rule for a step with no gateway lives in the one place that starts the broker.
- **Mark the tier of an attempt on the live broker in `_attempt`, right after `_tier_for_attempt` returns, and leave `_tier_for_attempt` a pure function.**: `_tier_for_attempt` is a pure choice with its own tests, and the attempt loop is the place that knows the tier of the turn that the shell runs in.
- **Record the spend of the broker in `BrokerSpend` of its own module, and convert it with `plus_shell` of `src/devops_cli/roadmap/implement/implement_step.py:class TierSpend`.**: `implement_step.py` imports the broker, so the broker must not import the tier record from it; the small record keeps one direction of import.
- **Close the broker first in the `finally` of `run_step`, before `end_step`.**: The token must stop working when the step ends, also when the step stops or raises.
- **Give the shell environment its own behavior group, verified by `tests/roadmap/implement/test_roadmap_implement_step.py`, and the step lifecycle of the broker its own behavior group, verified by `tests/roadmap/implement/test_roadmap_implement_job.py`.**: A behavior group's `verify` runs the module that holds its first failing test, and the test that asserts no AI key in the shell of a real job lives in the job module; one group that named both modules would leave the job test unrun.
- **Keep this item independent of #3823, #3827 and #5506, which build on its broker.**: `read_issue` of #3563 named #3823 and #3827 as items B and C of the same split and `find_issues` showed #5506 consumes the broker of #3820, so all three come after this item and none is a dependency of it.

## Rejected alternatives

- **A Caddy sidecar in front of the gateway.**: The body of #3820 states that `execve` sets the dumpable flag to 1 again and that the shell has the same user as the broker, so the shell could read `/proc/<pid>/environ`; the comment of #3563 records the same measurement of the flag in a child.
- **Pass the AI key to the shell.**: That undoes #2667, and the job process is not dumpable, which is the property that keeps the key away from the shell.
- **Store the AI key in a file that the broker reads.**: The shell can read the file, and the key would outlive the step.
- **Send the upstream request with a plain `httpx2.Client` of the broker module.**: The rule `net-raw-http-client` of `.ast-grep/rules/` fails the constructs row, and the connect would skip the egress check of the agent.
- **A path prefix such as /v1/* in the allowlist.**: A prefix lets the shell reach every gateway route under it, which is more than the two endpoints of the model of the agent and of rag-query.
- **Only POST /chat/completions in the allowlist.**: `devops ai rag-query` embeds its query, and `tests/ai/rag/test_embedding_providers.py:def test_gateway_embeddings_use_gateway_url_not_global_api_base` shows the engine send POST /embeddings.
- **A separate tool budget for shell calls.**: The endpoints are the same as the model call of the agent, so a second budget splits one cost across two records and hides spend from the step budget.
- **No accounting of shell calls.**: A shell call spends gateway tokens, and without a record the step budget and the tier record would understate the step.
- **Pass the broker address and the token as command-line arguments of the shell.**: Arguments are visible in process listings, and a later process can read the token.
- **Write the broker address and the token to a file in the worktree.**: The file persists after the step, and a later step can read it.
- **One long-lived token for every step of the run.**: It outlives the step and breaks the per-step limit of the issue.
- **A Unix domain socket for the broker.**: The issue asks for a loopback proxy, and the HTTP clients of the project expect a URL.
- **A fixed port on the pod address.**: Other pods can reach it, and the port can conflict with another listener of the pod.
- **A socket server of our own instead of FastAPI and uvicorn.**: `src/devops_cli/server/app.py` already builds a FastAPI app, and the pinned libraries cover the server and the client.
- **One group that gives the shell its variables and runs the end-to-end job test.**: The review of the plan showed that its `verify` ran only `tests/roadmap/implement/test_roadmap_implement_step.py`, so the job test that delivers the criterion of no gateway key in the shell never ran; the two behaviors now have a group each.
- **Mark the tier of an attempt inside `_tier_for_attempt`.**: That function is a pure choice with its own tests, and a side effect there would make it untestable alone; the attempt loop already holds the tier that the shell call runs under.

## Security

The step shell crosses a trust boundary: it holds a per-step token and the loopback broker address, and never the AI key of the job process. A person confirms that the allowlist stays the two pairs, that the broker binds only a loopback address, and that the broker widens no egress level for the shell. `tests/roadmap/implement/test_roadmap_implement_broker.py` fails when another path or method reaches the gateway, when an answer holds the key, or when the token works after the step ends, and `tests/roadmap/implement/test_roadmap_implement_step.py` fails when the shell environment or arguments hold a value of the key.
