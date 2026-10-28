# Design

## The seam

`k8s/api.py` holds the Protocols and the one real source. `KubernetesService` stays the process singleton that devops-cli calls; it takes a `KubernetesApiSource` and caches the `KubernetesApis` it connects for each resolved context.

- `KubernetesService(source)` builds a service over a given source. `KubernetesService.install(source)` replaces the process's service with one over that source, and returns it. `reset_instance()` removes it, so the next `get_instance()` builds a service over `KubernetesClientSource` again. The test floor already calls `reset_instance` after each test.
- `core_api(context)` and `custom_objects_api(context)` return the connected API objects, or raise `KubernetesContextError` when no connection can be made. The service's own methods call the same accessors.

## The configuration rule

`KubernetesClientSource.connect(context)` names the context to use: the resolved context, else the kubeconfig's current context. When the kubeconfig names that context, it builds the client with `new_client_from_config(config_file=<every KUBECONFIG entry>, context=<name>, persist_config=False)`. Otherwise it loads the pod's service account into a new `Configuration` with `InClusterConfigLoader(...).load_and_set(configuration)`. When neither applies, it raises `KubernetesContextError`, which names the context.

This is the rule `ui/data_providers.py` already documents, and the one the 2026-10-08 comment on #1315 proposes. `ui/data_providers.py`, `k8s/doctor.py`, `k8s/service_proxy.py` and `commands/k8s/cluster_context.py` keep their own loaders until #1334, #1322 and #1323 route them through the seam.

## The fake

`tests/support/fakes/kubernetes.py` fakes the SDK's API objects, not the service, so the service's caching, context resolution and projections run in every test.

- `FakeCoreV1(pods=, nodes=, events=, logs=, watch_events=, services=, pvs=, pvcs=)` keeps the constructor of `tests/k8s_fakes.py` and adds services, persistent volumes and claims. A read of a missing object raises `ApiException(status=404)`.
- `FakeCustomObjects` holds custom objects by group, version, namespace, plural and name, and `FakeVersion` answers `get_code`.
- `FakeCluster` is the source: it names its contexts and its current context, connects to its one set of API objects, and records each connect.
- `FakeCluster.unreachable()` makes every API call raise the error the real client raises when no server listens: `urllib3.exceptions.MaxRetryError`.
- Each fake records its calls in `calls`, as `(method, arguments)`.

## The contract suite

The real side is `KubernetesClientSource` over a kubeconfig in `tmp_path` whose cluster is `http://127.0.0.1:<port>`, served by a loopback server in the test. The server answers each request with the response recorded for its method and path in `tests/fixtures/kubernetes/recorded_responses.json`. The fake side is `FakeCluster`, seeded with the objects of the same recording. Each case runs one call through `KubernetesService` on each side and compares the projected result: names, statuses and the error's type and status.

## Rejected alternatives

- **Fake the service instead of the API objects.** Rejected on 2026-10-07 in #1315: a fake service would skip the service's caching, context resolution and projections in every test.
- **In-cluster first, as `load_config` did.** Rejected: inside a pod it ignores the configured context, which the comment of 2026-10-08 on #1315 records as a defect.
- **Keep the kubeconfig write of `switch_context`.** Rejected: `devops k8s context` runs `kubectl config use-context` first, so the write repeats it, drops the comments of the file, and reads only the first `KUBECONFIG` entry.
- **A live or local cluster for the real side.** Rejected in #1315 (Q26): no test reaches a cluster. kind needs a container engine and envtest downloads server binaries.
- **Keep `AppsV1Api` on the seam.** Rejected: no module calls it. A later caller adds it with its Protocol call and its contract case.
