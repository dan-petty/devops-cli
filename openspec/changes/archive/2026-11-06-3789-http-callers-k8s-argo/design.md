# Design

## Context

See proposal.md for the motivation and the scope (#3789, a slice of #3758, part 3 of #1314). The entry point is part 2 (#3755). The `dns` fixture is part 1 (#3752).

## Decisions

### 1. Callers pass the level as the first argument
- **Decision**: `http_client(level, ...)` takes the level as its first argument. The callers drop the `level=` keyword and keep every other argument.
- **Rejected**: a keyword-only `level` as in `new_http_client`. The entry point decided its own signature in #3755.

### 2. A test of a private function tests the public function that calls it
- **Decision**: the tests of `_execute_cluster_sync` and `_fetch_metric_value` call `sync_single_target` and `evaluate_rollout_gate`. The tests read the request that reached the `web` fake, and the result of the public function.
- **Rejected**: keep the private imports and only swap the double. A new or changed test imports no private name (`docs/TESTING.md`).

### 3. Keep the patches of other seams in files that this slice edits
- **Decision**: the patches of `ArgoCRDService._api`, `LiveResourceWatcher.watch`, `subprocess` and `ssl.SSLContext.load_cert_chain` stay where a file has them. They are not HTTP. Their seams (the Kubernetes API, the process runner) are other items of #1314.
- **Rejected**: move them in this slice. It would mix two seams in one pull request.

### 4. `tests/ai/mcp/test_k8s_logql.py` stays in place
- **Decision**: the file holds both the LogQL engine tests and the MCP tool tests. This slice changes its HTTP doubles only.
- **Rejected**: split it into `tests/k8s/` and `tests/ai/mcp/`. The split changes no HTTP double, and the AI slice of #3758 may edit the MCP tests.
