# Design: #7290

## Decisions

1. **One place for each resource.** devops-cli deletes each environment file and holds the product base `k8s/devops/` only. `.devops/project.toml` declares no `kubernetes.dir`, so `resolve_environment` goes on to `infra.repos`.
2. **No fallback.** `EnvironmentTree.require` and `require_applications` (`src/devops_cli/k8s/environment.py`) are the two guards. Each command calls the one for what it reads, and the error names the path, `--k8s-dir` and `infra.repos`. Product messages name no owner and no repository.
3. **An empty input is a failure.** A lint with no object, a render with no image and a tree with no Application exit non-zero. A push or a deploy reads the Secret table before it reaches the cluster.
4. **Product rows need no tree.** `devops config set <key> --generate` for a product key and `devops k8s bootstrap-roadmap-key` read `CLUSTER_SECRETS` only.
5. **The deploy of `repos onboard` reads a current tree.** The row writes the live cluster, so it refuses an environment checkout that is dirty or not at its `origin/main`, and it passes `--k8s-dir` to each child command.
6. **Checks keep their product part.** A gate check that protects `k8s/devops/` or product code stays in a surviving module and reads that folder by name: the NetworkPolicy checks, the registry check, the ServiceMonitor order, the dropped labels of `ai-spend.json`, the telemetry names, the webhook rate limit and the SLO groups. The root build of `k8s/devops/` and the dashboards folder each have their own check, because no other check builds them.
7. **One structure check.** `tests/gate/k8s_checks/product_tree.py` reads the paths of the git index, never a manifest value. Under `k8s/` it allows `k8s/devops/` and Markdown.
8. **Kept for the environment repository.** dan-petty/homelab uses `src/devops_cli/grafana/service_dashboard.py` with `grafana-foundation-sdk`, `k8s/devops/dashboards/` with its kustomization, and `k8s lint --k8s-dir`, `k8s image-pins` and `grafana dashboards lint <dir> <dir>`. Their forms do not change.
9. **Specs.** A requirement about a value, a manifest, an alert or a README section of the environment is removed. A requirement about product behavior stays and names a file of the environment tree, a fixture or `k8s/devops/`. A `MODIFIED` delta cannot drop a scenario, so a requirement that loses one is removed and added under a new name.
10. **Secret rows of the environment.** A requirement that says that the push writes a row of the environment, and names no deleted file, stays. It holds for the table of the environment tree, and the tests read `tests/fixtures/cluster-secrets.toml`.

## Rejected alternatives

- **Keep the fixture fallback of the Secret table.** `load_cluster_secrets_table` read `tests/fixtures/cluster-secrets.toml` in place of a missing file. That is a second copy of the environment rows, and a push could write the cluster from test data.
- **Keep the copy and the freeze check.** `tests/gate/k8s_checks/environment_freeze.py` refused an edit, but a person or an agent could still read the stale file or apply it with `kubectl apply -k k8s/monitoring`.
- **A pre-commit `fail` hook for the structure rule.** It runs at commit time. The table of `devops ci`, which CI runs, starts pre-commit only in the `hadolint` row, so a pull request with `--no-verify` commits would pass.
- **Keep the `charts` row with no check.** Both of its checks read the Tempo chart of the environment. A row that checks nothing reports a pass.
- **Let a command skip a missing folder.** `devops k8s image-pins` skipped a missing Application folder, so with no environment it resolved no image and exited 0.
