# Proposal: #6680

## Why
Closes #6680. `devops k8s deploy-stack` installs each Helm release with a fixed list of values files: the `values` and `product_values` of its row in `HELM_RELEASES_BY_STACK`. It reads only the chart version from the Argo CD Application of the release. The infra plan puts a values template of dan-petty/infra before the environment values in an Application: `$infra/helm/<chart>/values.yaml` at a tag, then `$values/...`. A bootstrap that gives Helm only the fixed files then installs a release that is not the release that Argo CD syncs.

## What Changes
- deploy-stack takes the values files of each release from `helm.valueFiles` of the chart source of its Application, in their order, and resolves each file with `SourceTrees.value_file`. A file of another repository is fetched at the `targetRevision` of its source before the deploy touches the cluster, and stays until the Helm releases are installed.
- `HELM_RELEASES_BY_STACK` keeps the name, the chart and the namespace of each release. Its 19 rows lose `values`, and the row `prometheus` loses `product_values`. The list of values files then has one place, the Application.
- `chart_sources` of `devops_cli.k8s.app_sources` replaces `chart_versions`. It gives the chart source of each Application: the version that it pins, its values files and its sources with a `ref`.
- `SourceTrees` gets the field `dry_run`: with it, as in the dry-run state, a fetch only records its commands. The dry run of deploy-stack sets it, so it fetches nothing. Its new key `details.source_fetches` lists each fetch that the real run makes.
- `--product-dir` no longer gives values files: the Application of `prometheus` names its second values file. The option still gives the manifests, the post-Helm files and the ConfigMap template of the product base.
- The helm commands and the values files change for a consumer, so the change carries a delta of `k8s-helm-deploy`.
- The change fits one pull request. Issue #6681 changes the manifests of deploy-stack later; this change leaves `MANIFESTS_BY_STACK` as it is.

## Capabilities
- `k8s-helm-deploy`: ADDED requirements "deploy-stack gives each chart the values files of its Application" and "deploy-stack fetches the values files of another repository before it touches the cluster".
- `k8s-helm-deploy`: MODIFIED requirement "deploy-stack dry run lists the Helm upgrade commands", because its scenario of the prometheus release takes the alert rules from `--product-dir`.

## Impact
- On the current tree, the dry run gives the same helm commands as before: each Application names, with the `values` ref of the origin, the files that the table named, in the same order.
- A tree whose Application names a values template of dan-petty/infra installs the chart with that template first. dan-petty/homelab#89 can then add the template to the Applications.
- deploy-stack reads the `origin` of the checkout of the tree (`git config`, a local read), also in a dry run. In a checkout whose `origin` is not the repository of a `values` ref, the real run fetches that repository, as `devops k8s image-pins` and the `argocd` check do. The tests that assert that a dry run starts no process leave out a local read, as `tests/commands/test_global_dry_run.py` does.
- `k8s/README.md` states where the values files of a release come from.

## Feasibility
- Code at origin/main `52126dbd4`: `HELM_RELEASES_BY_STACK` (`src/devops_cli/commands/k8s/stack_lifecycle.py:129`) holds the values files of each row, and `_release_at` (`:1211`) joins them under the tree and the product base. `chart_versions` (`src/devops_cli/k8s/app_sources.py:152`) reads only `targetRevision`.
- `SourceTrees.value_file` (`app_sources.py:125`) resolves `$<ref>/<path>` in the checkout for the origin, else in a fetch; `argocd_gate.py:129` and `image_pins.py:222` use it. A dry run fetches nothing (`_fetch` reads `is_dry_run()`).
- Census, with a PyYAML probe of `k8s/argocd/apps` and `k8s/argocd/bootstrap`: 20 Applications have a chart source, 19 of them have the name of a release of the table (`argocd-image-updater` has no row). Each of the 19 lists only `$values/...` files with the `values` ref `https://github.com/dan-petty/devops-cli`, and the list is the list of the table, in the same order. No Application sets `helm.values`, `valuesObject` or `parameters`.
- Base output: `uv run devops k8s deploy-stack --stack all --no-push-secrets --dry-run` gives 33 helm commands.
- The root callback clears the dry-run state for the own `--dry-run` of a command (`src/devops_cli/main.py:305`), so `SourceTrees` alone would fetch in `deploy-stack --dry-run`. A command that sets the state again leaves it on for the next call in the same process: `tests/commands/k8s/test_k8s.py` calls the `k8s` group directly, and its real deploy after a dry run then ran as a dry run. So `SourceTrees` takes the flag of the command.

## Existing Tool Considered
- Argo CD resolves the values files of an Application, but `argocd app manifests` reads a live Argo CD, and a bootstrap runs before Argo CD exists.
- Helm takes a URL after `--values`, but a raw file URL fits only one forge, and a private repository then needs a token in the URL. `SourceTrees` fetches with the git configuration of the host.
- The change reuses `SourceTrees` and `ref_sources`, as the issue asks. It builds about 40 lines; about 60k tokens and 1 hour to build, and a low cost to keep.
- The change deletes the `values` and `product_values` fields of the table, `chart_versions`, and the `product_values` clause of the product check of `_stack_roots`.
