# Design

## Decisions
- A test that reads a committed config file and asserts a value of it is deleted, not rewritten. A test of code that takes a committed file as input and asserts no value of it stays.
- A test that holds a safety rule (a security context, a network perimeter, no credential in a file, prune protection, nested timeouts) or agrees code with a manifest at run time stays unchanged as a gray case. The owner decides each one; the pull request names a proposed decision.
- Where a gray test also asserted a pinned version, only the version assert goes, so a Renovate update passes.
- `deploy-stack` reads the chart versions from the Applications under `argocd/apps` and `argocd/bootstrap` of the tree once for each run, and keys them by the name of the Application, which is the name of the release.
- The guard counts, for each test module, the tests that read a committed config file: through a path built from `REPO_ROOT`, a relative `Path`, a path reader of the module or `tests.support.k8s_tree`. A module-level constant, helper or fixture that reads one taints each test that uses it. A count per module keeps the allow list short and still refuses a new test.

## Rejected alternatives
- Rewrite each value test as a rule over all files: the owner asked for no value tests, and each rule is again a test of config.
- Keep the versions in `HELM_RELEASES_BY_STACK` and let Renovate update them with a custom manager: two places for one pin, and the comparison test blocks each update.
- An ast-grep rule as the guard: it cannot follow a path through a helper or a fixture of the module, and it cannot hold a count for each module.
