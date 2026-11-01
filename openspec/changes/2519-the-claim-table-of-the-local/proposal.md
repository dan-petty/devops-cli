# Proposal

## Why

Issue #2519: `CHART_CLAIMS` in `tests/core/test_k8s_local_path_placement.py` has the chart name as its key. No check ties an entry to the chart version that an Argo CD Application pins. A chart release can move the claim switch or the affinity path of a pod. The test then reads a value that the chart no longer uses, and it passes. The pod can bind its volume on the control-plane node.

The token test of #1652 solved this with a key of chart and version, and a check that the key set equals `pinned_charts()`. This change gives `CHART_CLAIMS` the same key and the same check.

## What Changes

- The key of `CHART_CLAIMS` becomes `tuple[str, str]`: the chart name and the version that the entry was read from. The table holds 18 entries, one for each chart that an Application pins.
- `_chart_sites` finds the entry of a chart by name and ignores the version, as `_chart_sites` in `tests/invariants/test_k8s_manifests.py` does.
- The test `test_every_chart_an_application_installs_states_its_claims` compares chart names with the keys. It cannot pass with tuple keys. The new test `test_the_claim_table_names_each_chart_at_the_version_that_an_application_pins` replaces it. It asserts that `pinned_charts()` and the keys of `CHART_CLAIMS` have an empty symmetric difference. This also catches a chart with no entry, which the old test caught.
- The paragraph about this test in `k8s/README.md` names the right test path and the version rule. The path in that paragraph lacks the directory `core/` since #2830 moved the test there.
- The change has no spec delta and sets `skip_specs: true`. It edits a test table and one document. No `devops` command, option or message, no manifest and no service changes. The base spec `local-path-volume-placement` keeps its scenario "An Application installs a chart that the test does not know": a chart with no entry at its pinned version still fails the test.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Tests: `tests/core/test_k8s_local_path_placement.py`.
- Documents: `k8s/README.md`, section "Local-Path Volume Placement".

## Existing Code to Keep

- `pinned_charts()` and `chart_values()` in `tests/support/k8s_tree.py`. The change reads them and edits neither.
- `_CHART_TOKENS`, `_chart_sites` and `test_the_chart_table_names_each_chart_at_the_version_that_an_application_pins` in `tests/invariants/test_k8s_manifests.py`. They are the model. The change edits none of them.
- The other eight tests of `tests/core/test_k8s_local_path_placement.py` stay as they are. They pass with the new key because `_chart_pods` reaches the table only through `_chart_sites`.
- The base spec `openspec/specs/local-path-volume-placement/spec.md` stays as it is.
- Change 2147 (open) edits the same test file, but only `_CONTROL_PLANE_CLAIM_EXEMPTIONS`. It does not touch `CHART_CLAIMS`.

## Feasibility

Checked on 2026-11-01 at `origin/main`, with the commands below.

- The table has the chart name as its key. `grep -n -E '^CHART_CLAIMS|^def _chart_sites|^def test_every_chart_an' tests/core/test_k8s_local_path_placement.py` prints `90:CHART_CLAIMS: dict[`, `171:def _chart_sites(chart: str, values: dict[str, Any]) -> tuple[ClaimSite, ...]:` and `261:def test_every_chart_an_application_installs_states_its_claims() -> None:`. The body of `_chart_sites` is `sites = CHART_CLAIMS[chart]`.
- The model exists. `grep -n -E '_CHART_TOKENS|_chart_sites|test_the_chart_table' tests/invariants/test_k8s_manifests.py` prints the table (line 277), the lookup `(sites,) = (sites for (name, _), sites in _CHART_TOKENS.items() if name == chart)` (line 484) and the test (line 592) with the assertion `sorted(pinned_charts() ^ _CHART_TOKENS.keys(), key=str) == []`. `grep -n 'def pinned_charts' tests/support/k8s_tree.py` prints line 60.
- The base is green. `uv run devops ci test tests/core/test_k8s_local_path_placement.py` prints `9 passed`.
- The table has 18 entries and `pinned_charts()` has 18 pairs. `CHART_CLAIMS` has no stale name. The pairs are argo-cd 10.9.6, argo-workflows 2.0.13, argocd-image-updater 1.3.1, cloudnative-pg 0.29.1, dcgm-exporter 4.8.4, gitea 12.7.0, grafana 14.0.1, k8s-monitoring 4.5.2, loki 20.0.2, mattermost-operator 1.0.5, open-webui 16.6.0, opentelemetry-collector 0.175.0, prometheus 29.35.0, prometheus-operator-crds 32.0.1, pyroscope 2.3.1, qdrant 1.19.1, tempo 3.1.0 and traefik 42.1.3.
- The old coverage test breaks with tuple keys. The expression of the old test, `{chart for chart, _, _ in chart_values()} - CHART_CLAIMS.keys()`, with tuple keys prints `['argo-cd', 'argo-workflows', 'argocd-image-updater', ...]` (one name for each chart): a set of names never meets a set of tuples. So the plan must replace that test, and it does.
- The entries are right at the pinned versions, so the new keys do not state a false fact. For each chart with claims, `helm show values <chart> --repo <url> --version <pinned>` shows the values that the table reads: `persistence.enabled` is `true` for gitea and `false` for grafana, pyroscope, tempo and traefik; `deploymentMode` is `Monolithic` and `singleBinary.persistence.enabled` is `true` for loki; `server.persistentVolume.enabled` and `alertmanager.persistence.enabled` are `true` for prometheus; `affinity` exists for gitea, grafana, open-webui, qdrant, tempo and traefik. The subcharts of open-webui (`helm pull`, then `tar xzf`) match the table too: `pipelines` has a `persistence` block and `affinity: {}`, and `ollama` has `persistentVolume.enabled: false` and `affinity: {}`. The subchart `alertmanager` of prometheus holds `persistence.enabled: true` and `affinity: {}`. For the eight empty entries, no chart turns a claim on: argo-cd has `redis-ha.enabled: false` and `redis-ha.persistentVolume.enabled: false`, argo-workflows has `persistence: {}`, opentelemetry-collector has `mode: ""` and `volumeClaimTemplates: []`, and the other five have no persistence value.
- The risk is real. `git log -G targetRevision --format='%h %ad %s' --date=short -- k8s/argocd/apps` shows commit 33b582d0 (2026-10-28) moved traefik from 41.6.0 to 42.1.3 and did not touch the table. The table was right by luck at 42.1.3. With the new key, the next bump of any chart fails until a person reads the claim values again.
- Nothing newer did or removed this work. `git log origin/main --since=2026-10-30 -- tests/core/test_k8s_local_path_placement.py tests/support/k8s_tree.py tests/invariants/test_k8s_manifests.py` prints only commits that do not touch `CHART_CLAIMS`. A search of open and closed issues for `CHART_CLAIMS` finds only #2519, its plan and the pull request of its first run. The first run (a Job) stopped, and its diff was discarded. The diff left `CHART_CLAIMS` empty, so it was no model for this change.
- The issue cites `openspec/changes/archive/2026-10-28-1652-no-unused-service-account-token/design.md`. `ls` shows that the file exists.

## Existing Tool Considered

No external tool covers this need. The need is a check on one test table of this repository against the pins of its own Applications. Renovate (#2577) proposes the bump of a chart pin, but it cannot read what a chart release moves inside a values file. The change reuses `pinned_charts()` and copies the key and the assertion of `_CHART_TOKENS`. It builds no helper and adds no dependency. It deletes one test (`test_every_chart_an_application_installs_states_its_claims`), which the new test replaces. The written cost is one pass over one 300-line test file and one paragraph: about 5,000 tokens to build, nothing to keep, and no new fix surface.

## Acceptance

Each criterion of the issue maps to a group of `tasks.md`:

- `version-keyed table` (the key of `CHART_CLAIMS` is a tuple of chart name and pinned version, and the keys equal `pinned_charts()`): group 1, task 1.2.
- `version mismatch fails` (a test fails when an Application pins a version that the table does not name): group 1, task 1.2 writes the test. The scenario "`pinned_charts()` returns a pair that is not a key" cannot run offline in a test of the real tree, so task 1.3 gives numbered steps that bump one pin and show the failure.
- `placement checks unchanged` (the placement tests pass with the new key): group 1, tasks 1.1 and 1.4.
- The issue also asks for an update of the existing coverage test: group 1, task 1.2. Group 2 keeps `k8s/README.md` true.
