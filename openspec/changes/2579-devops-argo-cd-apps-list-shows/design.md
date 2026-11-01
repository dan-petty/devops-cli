# Design

## Decisions

- **The Repo column shows the `repoURL` of the first entry of `spec.sources` when `spec.sources` is a non-empty list, and else the `repoURL` of `spec.source`.** Argo CD does the same: `HasMultipleSources` is `len(spec.Sources) > 0` and `GetSources` returns `spec.Sources` before `spec.Source` (`pkg/apis/application/v1alpha1/types.go`). The first source is the primary one, so the column stays narrow. No homelab Application has both fields today, so the order of the two fields changes no row that exists now.
- **Only `ArgoCDApp.from_api_item` changes.** It is the one reader of the Repo column (`src/devops_cli/commands/argo.py` line 250). `ArgoResourceState.from_manifest` has the same read, but nothing reads its `repo_url`, so a change there would be code with no output.
- **The help states the rule in the docstring of `cd_apps_list`.** The issue asks for a rule the help states. The docstring is the help text of the command, and the generated documents copy it.
- **A `spec`, a `source` or a `sources` entry that is not a dict gives an empty repository.** `test_argocd_app_from_api_item` already requires this for `spec` and `source`. The model never raises on a malformed payload.

## Rejected alternatives

- **Join the `repoURL` of every source with a comma.** The issue allows it, but the value is long: `argocd` has three sources. A table cell that wide wraps and hides the other columns. The first source is enough to name the Application.
- **Read `spec.source` first and use `spec.sources` only as a fallback.** It also fixes the 18 rows. It differs from Argo CD when an Application has both fields, because Argo CD syncs `spec.sources` then. The order above shows the source that Argo CD uses.
- **Also change `ArgoResourceState.from_manifest`.** The refine text of the issue lists it. `git grep -n "\.repo_url" -- src` shows no reader of that field, so the change would serve no output and no criterion of the issue.
- **Leave the column empty.** It keeps the defect that the issue reports.
