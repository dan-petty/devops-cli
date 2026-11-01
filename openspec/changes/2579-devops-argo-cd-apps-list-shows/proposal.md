# Proposal

## Why

Issue #2579 reports that `devops argo cd apps list` shows an empty Repo column for every Argo CD Application that has `spec.sources` (several sources) and no `spec.source`. `ArgoCDApp.from_api_item` reads `spec.source.repoURL` only. On the homelab, 18 of the 32 Applications have `spec.sources`, so 18 rows show no repository.

## What Changes

- `ArgoCDApp.from_api_item` (`src/devops_cli/models/argo.py`) reads the repository from the first entry of `spec.sources` when `spec.sources` is a non-empty list, and else from `spec.source`. Argo CD itself uses `spec.sources` first when it is not empty, so the rule gives the same source that Argo CD syncs. The rule is: the Repo column shows the first source.
- The help of `devops argo cd apps list` (the docstring of `cd_apps_list` in `src/devops_cli/commands/argo.py`) states that rule. The issue asks for "a rule the help states".
- Tests in `tests/commands/test_argo.py` cover the model, the table of the command and the help.
- The generated documents (`docs/commands/argo.md`, `docs/CLI_REFERENCE.md`, `docs/MCP_TOOLS.md`) take the new help text.
- Not in this change: `ArgoResourceState.from_manifest` also reads only `spec.source.repoURL`. No code reads the `repo_url` of an `ArgoResourceState` (see Feasibility), so the change leaves it as it is. The Repo column is the scope of the issue.
- The change fits one pull request.
- The change adds the capability `argo-cd-apps-list`, because the output and the help of a devops command change.

## Capabilities

### New Capabilities

- `argo-cd-apps-list`: which repository the Repo column of `devops argo cd apps list` shows for an Application with one source, with several sources and with none, and the help that states the rule.

### Modified Capabilities

None. No capability in `openspec/specs/` covers the output of `devops argo cd apps list`. `command-dry-run-class` and `configured-service-urls` name the command, but only for its dry run and its address.

## Impact

- Code: `src/devops_cli/models/argo.py`, `src/devops_cli/commands/argo.py`.
- Tests: `tests/commands/test_argo.py`.
- Documents: `docs/commands/argo.md`, `docs/CLI_REFERENCE.md`, `docs/MCP_TOOLS.md` (generated).
- Existing tests that must keep passing: `test_argocd_app_from_api_item` in `tests/commands/test_argo.py` (a `spec` or a `source` that is not a dict gives an empty repository), `tests/argo/test_argo_crd.py::test_states_tolerate_sparse_and_malformed_payloads`, `tests/commands/test_argo_dry_run.py`, `tests/commands/test_all_commands_help_dryrun.py`, `tests/ai/mcp/test_fastmcp_contracts.py`.
- Code that this change reuses: `ArgoCDApp` and its `repo_url` field, the row built in `_build_apps_table` (`app_info.repo_url`), and `format_argo_apps_table` (`src/devops_cli/output/formatters/tables.py`), which already has the Repo column. `cd_apps_get` (`devops argo cd apps status`) also calls `ArgoCDApp.from_api_item` and shows no repository, so it does not change.

## Feasibility

All commands ran on 2026-11-01 in a checkout at origin/main `0d2d0723`.

- The defect is in the code. `git grep -n "repoURL" -- src/devops_cli/models/argo.py` prints line 46 (`repo_url=str(source.get("repoURL", ""))`, where line 38 sets `source = spec.get("source", {})`) and line 165 (`ArgoResourceState`). Neither reads `spec.sources`.
- The issue names the class `ArgoAppInfo`. That name does not exist: `git grep -n ArgoAppInfo` prints nothing and exits 1. The class is `ArgoCDApp`, in the same file.
- The command uses this code. `src/devops_cli/commands/argo.py` line 250 calls `ArgoCDApp.from_api_item(item)` and line 259 puts `app_info.repo_url` in the Repo column. `format_argo_apps_table` (`src/devops_cli/output/formatters/tables.py`) defines the column.
- The count is right, and now higher. A read-only `kubectl -n argocd get applications -o json` on the homelab printed 32 Applications, of which 18 have `spec.sources`, 0 have both `spec.source` and `spec.sources`, and 0 have neither. The issue named 16 of 29 on 2026-10-29. The 18 are `argo-workflows`, `argocd`, `argocd-image-updater`, `cloudnative-pg`, `dcgm-exporter`, `gitea`, `grafana`, `k8s-monitoring`, `loki`, `mattermost-operator`, `open-webui`, `otel-collector`, `prometheus`, `prometheus-operator-crds`, `pyroscope`, `qdrant`, `tempo` and `traefik`. For example `argocd` has three sources: the chart repository `https://argoproj.github.io/argo-helm`, then two entries of the git repository (one with `ref: values`, one with no ref). `argo-workflows` has the chart repository, then the `values` ref.
- The manifests agree. `git grep -c "^  sources:\|^    sources:" -- k8s/argocd/apps` lists 18 files with a `sources:` key, in 31 files of that directory.
- The mechanism matches Argo CD. The source of `pkg/apis/application/v1alpha1/types.go` in argoproj/argo-cd (master) has `HasMultipleSources()` as `spec.SourceHydrator == nil && len(spec.Sources) > 0`, and `GetSources()` returns `spec.Sources` when that is true, else the single `spec.Source`. So `spec.sources` has priority when it is not empty, and its first entry is the primary source. The plan follows this order, which also holds when an Application has both fields. The source hydrator is out of scope: no homelab Application uses it.
- `ArgoResourceState.repo_url` has no reader. `git grep -n "\.repo_url" -- src` prints `src/devops_cli/commands/argo.py:259` (`ArgoCDApp`), `src/devops_cli/k8s/argocd_overrides.py:101`, which is another class, and `src/devops_cli/commands/repos.py:219`, which is another name (`HELP.repos.repo_url`). None reads `ArgoResourceState.repo_url`. The only call in `src/` of a method that returns an `ArgoResourceState` for an Application is `apply_application` in `src/devops_cli/commands/argo.py` (line 486), and it uses `.name` only. So the fix of that field would serve no output. The refine text of the issue names both methods, but only `ArgoCDApp` feeds the Repo column.
- Nothing newer did or removed this. `git log --oneline origin/main -3 -- src/devops_cli/models/argo.py` prints #2855, #905 and #335 only, and none reads `spec.sources`. A search of the issues for "spec.sources" finds only #2579, its plan PR #3003 (merged) and an open implementation PR for the same item (#3078); no other issue covers the Repo column.
- The first version of this plan named a flat test file for the argo model. No such file exists: `git ls-files tests | grep -i "models_argo"` prints nothing. `docs/TESTING.md` says that a new test joins the file that already tests the behaviour. `tests/commands/test_argo.py` holds `test_argocd_app_from_api_item` and the render tests of `apps list`.
- The help is the docstring. `HELP.argo.apps_list` in `src/devops_cli/lang/en/help.py` (line 698) has no reader: `git grep -n "apps_list" -- src` finds only the function names and the plan function. `devops argo cd apps list --help` prints the docstring of `cd_apps_list`. The docstring of `devops argo cd apps status` already has several paragraphs, and `devops docs generate` writes them into the three documents.

## Acceptance

Criteria of the issue, and the group of `tasks.md` that delivers each:

- Single-source Application: the Repo column shows `spec.source.repoURL`: group 1 (the implementation keeps this case, and a test row guards it).
- Application with `spec.sources` and no `spec.source`: the Repo column shows `spec.sources[0].repoURL`: group 1.
- Application with neither field: the Repo column is empty: group 1 (a test row guards it).
- "or the first source, with a rule the help states" (Expected behavior of the issue body): group 1 (the help task and the generated documents).
- Pending a person: none. The homelab check in Feasibility is read-only, and a person can repeat it with `uv run devops argo cd apps list` after the merge.

## Existing Tool Considered

No open tool covers this need. It is a defect in the field read of the project's own model, and the Argo CD API already returns `spec.sources` in the JSON that the model parses. The fix reads that field in the existing model. The written cost to build, keep and fix it: a few lines of code and three tests, under one hour of elapsed time. The change deletes no internal code.
