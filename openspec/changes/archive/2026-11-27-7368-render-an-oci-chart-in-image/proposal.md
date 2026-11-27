# Proposal: #7368

## Why

`devops k8s image-pins` stops when an Argo CD Application names a chart of an OCI registry (#7368). Argo CD writes such a source as a `repoURL` with no scheme, for example `ghcr.io/actions/actions-runner-controller-charts`. `_chart_command` in `src/devops_cli/k8s/image_pins.py` raises `ImagePinError` for it, because no Application used an OCI registry when the check was written. Some projects publish their charts only in an OCI registry. An environment repository that installs such a chart cannot pass the check, which its CI runs.

## What Changes

- A chart source whose `repoURL` is a registry path renders with `helm template <release> oci://<repoURL>/<chart> --version <targetRevision>`. The release name, the namespace, `--skip-tests` and the value files are those of a chart source of an https chart repository.
- A chart source of an `http` or `https` chart repository renders as before, with `--repo`.
- The check reads the `repoURL` as Argo CD does: a `repoURL` with no `//` part is a registry path. So a registry with a port, such as `registry.example.com:5000/charts`, is a registry path too. The check of today reads the host of such a path as a scheme.
- The refusal "names an OCI chart repository, which the check does not render" is removed. Its test becomes a test of the render command.
- `devops k8s catalog` renders each Application with the same function (`application_renders`), so it renders a chart of an OCI registry too.
- The module text of `src/devops_cli/k8s/image_pins.py` and the section "Image Pins" of `docs/CLUSTER.md` name the two repository forms.
- The behavior of a command changes, so the change has a spec delta.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `k8s-image-pins`: A chart of an OCI registry renders by its OCI reference

## Impact

- Code: `src/devops_cli/k8s/image_pins.py`
- Documents: `docs/CLUSTER.md`
- Tests: `tests/k8s/test_image_pins.py`
- Commands: `devops k8s image-pins` and `devops k8s catalog` render a chart of an OCI registry. The check gives Helm no credential of its own, as for an https chart repository.
- The other readers of a chart source: `git grep -n -e '"chart" in' -e 'get("chart")' -- src/devops_cli` gives 6 lines in 5 modules, and `git grep -n -e 'chart_sources(' -- src/` gives the definition and 1 caller. The design gives the result for each of them. None of them refuses a registry path.

## Feasibility

- Helm v4.3.2, the `helm` of the devtools image 1.3.1: `helm template arc oci://ghcr.io/actions/actions-runner-controller-charts/gha-runner-scale-set-controller --version 0.15.1 --namespace arc-systems --skip-tests` exits 0. The render has 300 lines and names the image `ghcr.io/actions/gha-runner-scale-set-controller:0.15.1`. With `--values <file>` and `replicaCount: 2` in the file, the render holds `replicas: 2`.
- `helm template arc gha-runner-scale-set-controller --repo oci://ghcr.io/actions/actions-runner-controller-charts --version 0.15.1` exits 1: `Error: looks like "oci://ghcr.io/actions/actions-runner-controller-charts" is not a valid chart repository or cannot be reached`. So a chart of an OCI registry needs the chart reference and no `--repo`.
- A version that the registry does not hold exits 1: `Error: failed to perform "FetchReference" on source: ghcr.io/actions/actions-runner-controller-charts/gha-runner-scale-set-controller:0.0.0-none: not found`. `_render_chart` puts the error of Helm after `helm template <release> failed:`, whatever the repository form.
- Argo CD (argoproj/argo-cd, `master` on 2026-11-27): `IsHelmOciRepo` in `util/helm/client.go` reads a `repoURL` with no `://` as an OCI registry, also `demo.goharbor.io:8080`. `PullOCI` in `util/helm/cmd.go` pulls `oci://<repo>/<chart>` at `--version`.
- Python 3.14: `urlsplit("ghcr.io/actions/actions-runner-controller-charts").netloc` and `urlsplit("registry.example.com:5000/charts").netloc` are empty, and `urlsplit("https://charts.example.com").netloc` is `charts.example.com`. `urlsplit("registry.example.com:5000/charts").scheme` is `registry.example.com`, so the scheme does not tell the two forms apart.
- A dry run: `run_subprocess` in `src/devops_cli/core/process.py` prints the command and starts no program, so the chart command of a registry path is printed and no request is sent.

## Existing Tool Considered

Helm covers the need: `helm template` pulls a chart from an OCI registry and renders it. The change builds no chart renderer and no OCI client. `urllib.parse.urlsplit` of the standard library reads the `repoURL`. The change deletes the refusal of an OCI chart repository in `_chart_command`.
