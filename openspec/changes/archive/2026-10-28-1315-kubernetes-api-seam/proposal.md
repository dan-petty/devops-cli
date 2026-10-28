# Proposal

## Why

Issue #1315: devops-cli reaches the Kubernetes API through `KubernetesService` and through four other loaders, and its tests reach the API by patching the SDK.

- `KubernetesService.load_config` tries the pod's service account first. Inside a pod it ignores the requested context, and it loads the client's global default `Configuration`, which every other loader also writes.
- `k8s/informer.py` and `k8s/service_proxy.py` read the service's private `_core_v1`.
- `switch_context` writes the kubeconfig a second time after `kubectl config use-context`. The write drops the comments of the file, and it reads only the first `KUBECONFIG` entry.
- `tests/test_k8s_service.py` patches `kubernetes.config`, `kubernetes.client`, `kubernetes.watch.Watch` and the service's own `load_config`. The one shared fake, `FakeCoreV1` in `tests/k8s_fakes.py`, has no contract suite, so nothing holds it to the real client.

## What Changes

- `src/devops_cli/k8s/api.py` is the seam. The Protocols `CoreApi`, `CustomObjectsApi` and `VersionApi` name the 18 calls devops-cli makes on the SDK's API objects. `KubernetesApiSource` names where the objects come from: `contexts()` and `connect(context)`.
- `KubernetesClientSource` is the one real source. It has one configuration rule: the kubeconfig when the kubeconfig names the resolved context, else the pod's service account. It reads every `KUBECONFIG` entry when it is called, and it builds each `ApiClient` with its own `Configuration`, so it writes no global default.
- `KubernetesService` takes a source. `KubernetesService.install(source)` makes the process's service one that takes its API objects from that source, until `reset_instance`. `core_api(context)` and `custom_objects_api(context)` are its public accessors. The informer and the service proxy use `core_api`, and no module reads a private attribute of the service.
- `switch_context` checks that the kubeconfig has the context and points the in-process clients at it. It does not write the kubeconfig: `kubectl config use-context` owns the file.
- The unused `AppsV1Api` client and `_get_kubeconfig_path` are deleted.
- `tests/support/fakes/kubernetes.py` is the shared fake: `FakeCluster`, a source, over `FakeCoreV1`, `FakeCustomObjects` and `FakeVersion`, with the builders of `tests/k8s_fakes.py`. It covers each Protocol call, answers a missing object with the SDK's `ApiException` and its status, can refuse every call as an unreachable API server does, and records each call. The `cluster` fixture installs it. `tests/k8s_fakes.py` is deleted, and its importers change only their import.
- `tests/k8s/test_kubernetes_contract.py` runs each case against the fake and against the real client, which reads recorded API responses from a loopback server that the test owns, through a kubeconfig under `tmp_path`.
- `tests/test_k8s_service.py` drives the service through the fake, the real source over a kubeconfig in `tmp_path`, or the contract suite. It patches no `kubernetes` name and no method of the service.
- The configuration rule and the kubeconfig that `switch_context` no longer writes are behavior a user sees, so the change carries a spec delta: the new capability `k8s-api-connection`.
- This change fits one pull request.

## Capabilities

### New Capabilities

- `k8s-api-connection`: how devops-cli connects to the Kubernetes API: which configuration it uses, and what a context switch changes.

## Impact

- `src/devops_cli/k8s/api.py` (new), `src/devops_cli/k8s/service.py`, `src/devops_cli/k8s/informer.py`, `src/devops_cli/k8s/service_proxy.py`, `src/devops_cli/k8s/__init__.py`.
- `tests/support/fakes/kubernetes.py` (new), `tests/k8s/test_kubernetes_contract.py` (new), `tests/fixtures/kubernetes/` (new), `tests/test_k8s_service.py`, `tests/conftest.py` (docstring), and the importers of `tests/k8s_fakes.py`, which is deleted.
- `docs/TESTING.md`.

## Feasibility

- Measured on origin/main 0137f231: `k8s/service.py` loads the pod's service account first (`load_config`), builds `AppsV1Api` that no module calls, and rewrites the kubeconfig in `switch_context`. `k8s/informer.py:107` and `:202` and `k8s/service_proxy.py:436` read `_core_v1`. Seven test modules import `tests/k8s_fakes.py`.
- The kubernetes client 36.0.3 (the pinned version) gives what the seam needs: `config.new_client_from_config(config_file=..., context=..., persist_config=False)` returns an `ApiClient` with its own `Configuration`; `config.incluster_config.InClusterConfigLoader(token_filename=..., cert_filename=...).load_and_set(configuration)` loads a service account into a given `Configuration`; `list_kube_config_contexts(config_file=...)` and `load_kube_config` read each `:`-separated `KUBECONFIG` entry through `KubeConfigMerger`. `KUBE_CONFIG_DEFAULT_LOCATION` is read once, when the module is imported, so the source passes the paths itself. `client.Configuration()` does not copy the global default in this version.
- The calls devops-cli makes on the API objects, counted with grep on origin/main: on `CoreV1Api`, `list_node`, `list_namespaced_pod`, `list_pod_for_all_namespaces`, `read_namespaced_pod_log`, `list_namespaced_service`, `read_namespaced_service`, `list_namespaced_event`, `list_event_for_all_namespaces`, `read_persistent_volume`, `patch_persistent_volume`, `delete_persistent_volume` and `read_namespaced_persistent_volume_claim`; on `CustomObjectsApi`, `list_`, `get_`, `create_`, `patch_` and `patch_..._status` of a namespaced custom object; on `VersionApi`, `get_code`. No module calls `AppsV1Api`, lists namespaces or reads deployments, so the Protocols and the fake leave them out.
- Overlap, checked on 2026-10-28: #1322, #1323 and #1334 route the other loaders (`k8s/service_proxy.py` and `k8s/doctor.py`, `commands/k8s/cluster_context.py`, `ui/data_providers.py`) through this seam and depend on it; #2167 names the fakes only. No open item owns the seam itself. #1312, the dependency, is closed. No `unreachable` mark names the Kubernetes API server, and #1309 is closed as not planned, so no marker or ceiling changes.
- The recorded responses are written in the API's wire format from the Kubernetes API reference, with `example.com` names and documentation-range addresses. A capture from a disposable local cluster is a step for a person.

## Existing Tool Considered

- The official `kubernetes` client is the real side; the change adds no client.
- No maintained fake of the Python client exists. envtest and kind run a real API server, which a test may not start (kind needs a container engine, and envtest downloads `kube-apiserver` and `etcd`). A loopback server that replays recorded responses is the real side, as the GitHub session's contract suite does.
- The fake is the promoted `FakeCoreV1`, extended to the Protocol calls. Its cost to build, keep and fix, as AGENTS.md asks: about 120k tokens and half a day to build with its contract suite; upkeep is one recorded response and one fake method for each new call devops-cli makes.
- The change deletes `KubernetesService._get_kubeconfig_path`, the kubeconfig write of `switch_context`, the unused `AppsV1Api` client, the service's global-default configuration loads, and `tests/k8s_fakes.py`.
