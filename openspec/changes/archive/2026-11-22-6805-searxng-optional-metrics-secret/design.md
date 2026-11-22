# Design

## Decisions
- **The reference is `optional: true`, and the script writes `''` for a missing or empty password.**: The kubelet then starts `render-settings` without the Secret and leaves `SEARXNG_METRICS_PASSWORD` out. An empty `general.open_metrics` turns `/metrics` off in SearXNG (HTTP 404). The script reads `${SEARXNG_METRICS_PASSWORD:-}`, because `set -u` stops on a variable that is not set.
- **The script logs one line to stderr that names Secret `devops/searxng-metrics-auth`.**: `kubectl logs -c render-settings` shows the line, so a person sees why the endpoint is off.
- **The render check runs in the `k8s` row of `devops ci`, not in pytest.**: The check reads the rendered manifests of `k8s/devops/searxng/` and starts `sh`. `docs/TESTING.md` keeps both out of pytest and puts a check of committed files in a row of `devops ci`. The check models the kubelet: it writes the keys of the ConfigMap volume as files, makes each `emptyDir` empty, gives each mount path its own directory, resolves the variables from the Secrets of the scenario, and refuses a required reference to a missing Secret as the kubelet does.
- **Entry `password` of row `devops/searxng-metrics-auth` is not required, and `OPTIONAL_FEATURE_SECRETS` names the row.**: A required entry with no value stops the whole push, so `deploy-stack --stack devops` stopped on a metrics password. The README rows come from the table, so the row now says `no` and `skip with a warning`.
- **The ServiceMonitor stays.**: When the Secret is pushed, the scrape works with no other change.

## Rejected alternatives
- **A pytest test of the script.**: `tests/gate/tree_checks/config_values.py` refuses a test that reads a file under `k8s/`, and the floor of `docs/TESTING.md` keeps real child processes out of pytest.
- **A generator for the password, so that the push makes it.**: It changes who owns the value that #4201 chose to type. The issue asks only that the pod start without the Secret, and the owner can decide a generator in its own item.
- **A ServiceMonitor with no basic auth while the Secret is missing.**: SearXNG refuses `/metrics` without the password, and Alloy reads the Secret only to build the target. A second monitor or a patch adds a state that Argo CD would remove.
- **A failed scrape and an alert that names the missing Secret.**: The issue expects one, but Alloy makes no target when the Secret is missing (its log of 2026-11-22), so `up` has no series and `TargetDown` cannot fire. An alert on the Alloy component error is outside the acceptance criteria of the issue.
