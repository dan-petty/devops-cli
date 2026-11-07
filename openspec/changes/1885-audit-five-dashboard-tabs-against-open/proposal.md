# Proposal

## Why

The owner decided on 2026-10-22 that the direction to replace custom code with open tools also covers the five dashboard tabs, and no audit compares them with the tools that do the same job. Issue #1885 writes that audit, records the cost of each replacement, and drafts one follow-up issue for each tab that an open tool can replace.

## What Changes

- Add `docs/DASHBOARD_TABS_AUDIT.md` with one section for each of the Kubernetes, Docker, Telemetry, Valkey and Logs tabs.
- State in each section what the tab does that the open tool does not, the lines a replacement deletes, the pin and the config to ship, the request cost and the person-run steps.
- Record in each section the reason a tab stays when no open tool covers its work.
- Add a summary table and a follow-up section that gives each replaceable tab its issue title, its body and the `devops gh issues create` command that a person runs.
- Link the page from `README.md` and `docs/index.md`, so the documentation walk from the agent router reaches it.
- Change no UI code and no test, as the issue asks, so the pull request holds documents only.
- The change adds documents and files no code, so it has no spec delta: a document changes no behavior that a consumer observes.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Documents: `docs/DASHBOARD_TABS_AUDIT.md`, `README.md`, `docs/index.md`

## Feasibility

- The earlier reply was refused because a What Changes item named the UI package, which no group changes; the list now names only the two documents that a group writes and the two lists that a group edits.
- `probes` confirms the cited lockfile: The path `src/devops_cli/tools_lock/tools.lock` is a file of the staging commit.
- `probes` confirms the cited guide: The path `docs/DEVCONTAINER_USAGE.md` is a file of the staging commit, and The path `CONTEXT.md` is a file of the staging commit.
- `probes` also says The path `design.md` is no file at the root of the staging commit, and The path `tasks.md` is no file at the root of the staging commit. Those names belong to the change folder, which the stage job writes and no task group may change, so the audit goes to a hand-written page under docs and no code compensates for the root path.
- The five tabs hold: `src/devops_cli/config/constants.py:3867:CONST_DASHBOARD_DOMAINS: Final[tuple[str, ...]] = (` lists k8s, docker, telemetry and valkey, and `src/devops_cli/ui/dashboard.py:215:with TabPane("Logs (l)", id=CONST_LOGS_TAB_ID):` adds the Logs tab.
- `list_files` of `src/devops_cli/ui` returned 12 modules and `list_files` of `tests/ui` returned 31 test modules, which is the scale that the issue states.
- The Kubernetes tool is pinned: `src/devops_cli/tools_lock/tools.lock:386:version = "0.51.0"` sits under `[binary.k9s]`, and `src/devops_cli/ui/widgets.py:class K8sPanel` with `src/devops_cli/ui/data_providers.py:def fetch_k8s_status` is the code that the section compares with k9s.
- `search_code` for `lazydocker` answered `No match.`, so no file of the commit pins lazydocker and the Docker section records the person-run release check instead of a version.
- The Telemetry and Logs tools are pinned: `k8s/argocd/apps/grafana.yaml:13:targetRevision: 14.0.1` pins the Grafana chart, `list_files` of `k8s/monitoring/dashboards` returned 15 dashboard JSON files and the `kustomization.yaml` that loads them, and `k8s/logging/loki-values.yaml` with `k8s/argocd/apps/loki.yaml` holds the Loki values and chart pin.
- The Valkey client is in the cluster guide: `k8s/README.md:87:kubectl -n llm exec -it svc/valkey -c valkey -- sh -c 'VALKEYCLI_AUTH="$VALKEY_PASSWORD" valkey-cli ping'`, and `src/devops_cli/ui/data_providers.py:def fetch_valkey_status` is the code that the section compares with it.
- A new page needs no inventory entry, because `src/devops_cli/docs/inventory.py:def document_class` makes the hand-written class the complement of the other classes; the page still needs a link, because `tests/invariants/test_agents_md_claims.py:def test_every_hand_written_and_generated_document_is_within_two_links_of_agents_md` fails for a page that no chain of two links reaches, and `AGENTS.md:29:[README.md](README.md)` puts `README.md` one link away.
- `find_issues` with the words dashboard tabs k9s lazydocker listed only #1885, so no open item changes the same tabs and the plan depends on none.
- Precondition: `uv run devops ci docs` needs a checkout of the repository, and every group runs it in the worktree of the branch.
- Precondition: `uv run devops ci test tests/invariants/test_agents_md_claims.py` needs a checkout of the repository.
- Precondition: `devops gh issues create` needs a client of GitHub and a checkout of the repository; a person runs it after the merge and no group runs it.
- Precondition: a read of the k9s, lazydocker, Grafana or Loki release page needs a network; the runner has none, so the audit leaves that read to the person-run steps.
- Precondition: a count of the cluster and Prometheus requests that k9s and Grafana make needs a client of the cluster; the runner has none, so the audit counts the tab's requests from its code and leaves the tool's count to the person-run steps.
- First checks: `uv run devops ci docs` for the page and the `devops` commands it names, and `uv run devops ci test tests/invariants/test_agents_md_claims.py` for its links.

## Existing Tool Considered

k9s 0.51.0, Grafana 14.0.1 with the dashboards of `k8s/monitoring/dashboards/`, the Loki datasource and `valkey-cli` from the `valkey-tools` package are the open tools that the audit compares with the tabs, and lazydocker is the candidate for the Docker tab; the change adopts a tool for each tab and builds none.

## Dependencies

None.
