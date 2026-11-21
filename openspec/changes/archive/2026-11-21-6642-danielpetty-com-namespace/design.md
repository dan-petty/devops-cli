# Design

## Decisions

- **A project of its own.** AppProject `danielpetty-com` admits only the site repository and only namespace `danielpetty-com`. It sets `clusterResourceWhitelist: []`, as project `trial` does, so an Application of the site writes no cluster-scoped object. `namespaceResourceBlacklist` holds `Role` and `RoleBinding` of group `rbac.authorization.k8s.io`, so the site repository cannot give a ServiceAccount more access in its namespace.
- **The namespace comes from this repository.** The project of the site cannot write a Namespace, so the root kustomization declares it. `Prune=false,Delete=false` keeps the namespace and its data when the declaration changes. The namespace carries `app.kubernetes.io/part-of: devops-cli-stack`, as each namespace of the root kustomization does.
- **The stack takes the name of the namespace.** `deploy-stack` pushes a detached stack only where a namespace with the name of the stack exists. So stack `danielpetty-com` goes into `DETACHED_STACKS`, and `deploy-stack` never deploys it.
- **Keyring-only keys.** No setting of the CLI reads the note key or the GitHub token: only the event-stream pod does. So the row reads the keyring keys `danielpetty_com_note_api_key` and `danielpetty_com_github_token` directly, as `searxng_secret_key` does. The note key has a generator, because an agent writes no secret value. The GitHub token is optional and has no generator: a person makes it on GitHub, and without it the harvester uses the anonymous rate limit of the GitHub API.
- **Orphans.** Project `danielpetty-com` warns on orphans and ignores Secret `event-stream`, which the push writes and no Application tracks. Project `homelab` ignores Secret `repo-danielpetty-com` in namespace `argocd`, as it ignores `repo-homelab`.
- **One egress port.** The monitoring perimeter gets egress to namespace `danielpetty-com` on TCP 9090 only, the metrics port of dan-petty/danielpetty.com#28.
- **The project review does not read the site.** The setting `roadmap.project_review.namespaces` lists the namespaces of this project (#6615). Namespace `danielpetty-com` holds the workloads of another project, so the default list does not get it. Its comment says so.

## Rejected alternatives

- **The site in project `homelab`.** Project `homelab` has `clusterResourceWhitelist` `group: '*', kind: '*'` (`k8s/argocd/apps/projects.yaml`), so the site repository could write any cluster-scoped object. Rejected.
- **The namespace in the site repository.** With `clusterResourceWhitelist: []`, Argo CD refuses a Namespace from an Application of the project. A whitelist entry for `Namespace` would let the site repository make any namespace. Rejected.
- **Managed credentials for the two keys.** A managed credential is a Settings option (`keyring_names()`), and the invariant test `test_keyring_sources_are_managed_keys_or_declared_keyring_only` requires each managed key to back an option. No CLI code reads these values, so an option would be dead configuration. Rejected.
- **A table row for the repository Secret `repo-danielpetty-com`.** The owner makes `repo-homelab` by hand with the values of the GitHub App `devops-cli-argocd` (`k8s/README.md`, GitOps), and the issue keeps one form for both repository credentials. Rejected.
- **The Argo CD Application in this change.** A pod that reads a missing Secret does not start, so a person pushes the Secret before the merge of the manifest that reads it (`docs/SERVICE_PATTERNS.md` CF4, CF5). #6644 adds the Application after the push. Rejected here.
