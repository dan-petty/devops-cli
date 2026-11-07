# Design

## Context

See proposal.md for the motivation and the counts (#4086, group 1 of #3769). The change edits tests, and three small paths under `src/devops_cli/commands/k8s/` that only the patches needed.

## Decisions

### 1. `contexts` and `status` read through `KubernetesService`

- **Decision**: `contexts` calls `KubernetesService.get_instance().list_contexts()` and `status` calls `list_nodes()`. `_k8s_clients` has no caller then, and it is deleted with its two tests. The `cluster` fixture serves both commands, and a failure test uses `cluster.unreachable()` for the API and a broken `KUBECONFIG` file for the real source.
- **Alternative considered**: keep `_k8s_clients` and patch `kubernetes.client.CoreV1Api` in the tests.
  - *Rejected*: `docs/TESTING.md` allows a patch of an SDK object only for an edge that no seam reaches. `KubernetesService` is the seam, and every other command of the group already uses it (`rg -n "KubernetesService" src/devops_cli/commands/k8s`).

### 2. The port-forward child starts through `spawn_detached`

- **Decision**: `_launch_port_forwards` calls `spawn_detached(cmd, isolate_env=False)`. `ProcessFake` records the call with `detached` set, and a test reads the argv from there. `DefaultProcessRunner.spawn_detached` starts the child with `start_new_session=True`, so the forward still runs in a session of its own. `isolate_env=False` hands the child the whole ambient environment, as the old call did with `subprocess.Popen` and no `env`.
- **Alternative considered**: keep `subprocess.Popen` and patch it in the tests.
  - *Rejected*: the floor refuses a real `Popen`, and `docs/TESTING.md` names `spawn_detached` as the one start of a detached child. The old test of the session read the source text of `networking.py` to find `start_new_session=True`. The new one reads `detached` on the recorded call.
- **Alternative considered**: `spawn_detached(cmd)` with the default `isolate_env=True`.
  - *Rejected*: `build_subprocess_env` keeps only the allowed variables, so kubectl could lose `KUBECONFIG`. The change would alter the child.

### 3. A TCP probe has a fixture of its own

- **Decision**: `tcp_probe` replaces `socket.create_connection`, refuses every probe until a test calls `listen` or `listen_where`, and records each probe. The old tests set the answer of a private function (`_verify_url_reachability`) in each test; they now set the answer of the network.
- **Alternative considered**: bind a loopback listener for each address.
  - *Rejected*: the commands probe addresses such as `192.0.2.49:30080`, and the floor refuses a connect to any loopback port that the test does not bind.

### 4. A deploy test scripts the world of kubectl once

- **Decision**: a test that pushes Secrets installs `KubectlWorld` (`tests/cluster_secret_fakes.py`) as the answer of `process_fake`. It answers `helm version`, the namespaces, the Secrets and the server-side apply. A test that pushes nothing uses `--no-push-secrets` and answers only `helm version`. The Argo CD state is an Application object in `cluster.custom_objects`, so `_is_cluster_argo_managed` runs for real.
- **Alternative considered**: keep the patches of `push_for_stacks` and `require_keyring_for_push`.
  - *Rejected*: they are the patches that this item removes, and they hid the order of the push against the other writes. The new tests read that order from the recorded calls.

### 5. The tests of a private helper stay

- **Decision**: a test of a private function of `commands/k8s/` (for example `_parse_minikube_service_url`) keeps its import. Its edges go to the fakes. Moving the logic into a domain package would change what the test checks, and it is another item.
