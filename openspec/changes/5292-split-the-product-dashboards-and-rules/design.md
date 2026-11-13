# Design

## Decisions

- **The product dashboards have a kustomization of their own, and the environment kustomization lists it.** The ConfigMap keeps its name, namespace, labels and files, so the render of `k8s/monitoring` stays the same bytes, and Application `monitoring` stays its owner. The copy to the private repository can then name the folder as a remote resource of devops-cli.
- **The product rules are a second values file under a new `serverFiles` key.** Helm merges maps and replaces lists, so a second file that set `serverFiles."alerting_rules.yml".groups` would replace the environment groups. A new key keeps both lists. The chart writes each key to the ConfigMap, and `rule_files` names it.
- **The environment values set `rule_files`.** The environment decides which rule files its server loads. The product file holds only its rules, so a second environment can give the chart the product file without other changes.
- **`HELM_RELEASES_BY_STACK` holds a list of values files for each release.** Each release has the same shape, a `TypedDict` named `StackRelease` (the name `HelmRelease` is already a class of `devops_cli.argo.helm_records`). The Argo CD test compares the list with the `valueFiles` of the Application, in order.
- **`devops grafana dashboards lint` takes several paths.** A default of two folders needs a list argument. One run over both folders keeps the check of a uid that two files share. `sync --dir` stays one folder, and its default is both folders.
- **The test reader merges the values files of a chart source.** The checks of the chart pods (token roles, volume placement) read the values that the chart gets. A file read alone with the chart defaults gives false findings: the product file alone turns on the pushgateway and the server claim of the defaults.

## Rejected alternatives

- **Keep the product rules in `alerting_rules.yml` and let the second file add groups.** Helm replaces the list `groups`, so the second file removes the environment groups. `helm template` with such a file showed only the groups of the last file.
- **Use the chart value `ruleFiles` for the product rules.** `templates/cm.yaml` writes each key of `ruleFiles` as a string with `toYaml | indent 2`, for rules with Prometheus label templates. It adds no entry to `rule_files`, so the environment must still name the file, and the rules become a string that no test reads as YAML.
- **List `dashboards` in `k8s/devops/kustomization.yaml`.** Application `devops` then takes the ConfigMap that Application `monitoring` owns, and the two Applications sync it in turn (the risk "Ownership change by accident" of the plan).
- **A new key of `config.yaml` for the dashboard folders.** #5131 makes the environment paths settings of the infra repository. A setting now would be a second, short-lived path.
- **Merge the values with a library.** No dependency of the project has a merge of mappings with the semantics of Helm, and the merge is for test readers only.
