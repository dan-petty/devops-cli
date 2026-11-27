# Design

## Decisions

- **Helm pulls and renders the chart.** For a registry path, `_chart_command` gives Helm the chart reference `oci://<repoURL>/<chart>` in place of the chart name and `--repo`. The other arguments do not change: the release name, `--version`, `--namespace`, `--skip-tests` and one `--values` for each value file. Argo CD builds the same reference (`PullOCI` in `util/helm/cmd.go`: `fmt.Sprintf("oci://%s/%s", repo, chart)`).
- **A `repoURL` with no `//` part is a registry path.** The predicate is `not urlsplit(repo).netloc`. It gives the result of `IsHelmOciRepo` of Argo CD for each form that an Application holds: `ghcr.io/example/charts` and `registry.example.com:5000/charts` are registry paths, and `https://charts.example.com` is a chart repository.
- **The `repoURL` and the chart name go to Helm as they are.** The check adds no rule for a slash at the end of a `repoURL` or for a wrong name. Argo CD joins the two parts with one slash and no other change. Helm refuses a wrong reference, and `_render_chart` reports the error of Helm.
- **The error text does not change.** `_render_chart` raises `ImagePinError` with `helm template <release> failed:` and the error of Helm. The first three words of the command are the same for the two repository forms.
- **A dry run needs no new code.** `run_subprocess` prints the command and returns a planned result when the dry-run state is on. `_render_application` keeps the command in `ImagePins.planned`. The process fake of the tests returns the planned result and prints nothing, so the test reads `ImagePins.planned`. A dry run of the command with the real Helm on `PATH` shows the printed line.
- **The other readers of a chart source keep their code.** The census gives five readers besides `application_renders`:
  - `chart_sources` (`src/devops_cli/k8s/app_sources.py:165`) reads `targetRevision` and `valueFiles`, and never `repoURL`.
  - Its one caller, `_collect_deploy_targets` (`src/devops_cli/commands/k8s/stack_lifecycle.py:1402`), takes the chart of each release from the table `HELM_RELEASES_BY_STACK`. It takes only the version and the value files from the Application.
  - `_check_helm_source` (`src/devops_cli/k8s/argocd_gate.py:117`) reads the value files only.
  - `_rendered_releases` (`src/devops_cli/argo/helm_records.py:179`) reads the release name of each live Application only.
  - `_render_app_objects` of `devops k8s catalog` (`src/devops_cli/k8s/catalog.py:687`) renders with `application_renders`, so this change covers it.
  - `collect_catalog_charts` (`src/devops_cli/k8s/catalog.py:303`) gives the dry-run plan of `devops k8s catalog` its charts. The plan of that command writes a `helm template` line of its own, which is not the command of the run. #7371 holds this.

## Rejected alternatives

- **`helm template <release> <chart> --repo oci://<repoURL>`.** Helm v4.3.2 exits 1: `Error: looks like "oci://ghcr.io/actions/actions-runner-controller-charts" is not a valid chart repository or cannot be reached`. `--repo` names an `http` or `https` chart repository only.
- **Keep the test `not urlsplit(repo).scheme`.** `urlsplit("registry.example.com:5000/charts").scheme` is `registry.example.com`, so a registry with a port would get `--repo`, which Helm refuses. `IsHelmOciRepo` of Argo CD reads `demo.goharbor.io:8080` as an OCI registry.
- **`helm pull` into a folder, then `helm template <folder>`.** `helm template` pulls the chart itself, so the second command and the folder add code and no result.
- **An OCI client in Python that reads the chart from the registry.** Rule 3 of AGENTS.md asks for the open tool. Helm reads the registry, verifies the chart and renders it in one command that the check starts today.
- **Change the dry-run plan of `devops k8s catalog` in this change.** `_render_dry_run` in `src/devops_cli/commands/k8s/catalog.py:30` writes `helm template <application> <chart> --repo <repoURL> --version <version>` for each chart. That line has no namespace, no `--skip-tests` and no value file, and it names the Application and not the `releaseName`. So it differs from the command of the run for an https chart repository too. The cause is a second copy of the command, and a change of the registry form alone does not remove the copy. #7371 asks for one function for the plan and for the run.
