# Design

## Decisions

- **Add the affinity and remove the exemptions in one group.** In a trial copy, each half alone made the placement test fail. Without the exemptions and without the affinity, `test_every_chart_pod_on_a_claim_keeps_off_the_control_plane_node` names the three pods. With the affinity and the exemptions, `test_every_exemption_names_a_pod_on_a_claim_that_stays_on_any_node` fails, because it requires an exempt pod to lack the affinity. One group keeps the test green after each group.
- **Keep `_CONTROL_PLANE_CLAIM_EXEMPTIONS` as an empty table.** The base spec ("A pod in the test's table of exemptions SHALL be the only exception", and the scenario "An exemption is stale") and the README describe the table. A later chart can mount a claim before its volume moves, and the README procedure says to add an entry for it. The issue allows "empty or gone". An empty table is the smaller change.
- **Copy the affinity block of the other pods.** The `affinity` block of `k8s/monitoring/pyroscope-values.yaml` and the `alertmanager.affinity` block of `k8s/monitoring/prometheus-values.yaml` hold the block and its comment. The test checks this form (`keeps_off_the_control_plane`).
- **No test is added.** The existing placement test is the check. The change adds no behavior of `src/`. The first task of group 1 shows the existing check fails when the affinity is missing.
- **The move of the volumes is a step of a person, and it is done.** A person moved the three volumes with `devops k8s volume move` before this change. The move scales Grafana, Prometheus and Loki to zero, which an implementation Job does not do. The plan holds only the check after the merge, and it builds no code for the move, because `devops k8s volume move` exists.

## Rejected alternatives

- **Change `CONST_K8S_CONTROL_PLANE_CLAIM_EXEMPTIONS` in `src/devops_cli/config/constants.py`.** Rejected: `git grep -n CLAIM_EXEMPTIONS -- src` prints nothing. The constant of the issue does not exist.
- **Add the affinity first and remove the exemptions in a second group.** Rejected: with the affinity and the exemptions, the stale-exemption test fails (see the first decision).
- **Remove the exemptions first and add the affinity in a second group.** Rejected: with the exemptions removed and no affinity, the chart-pod test fails and names the three pods.
- **Delete the exemption mechanism (the table, the stale-exemption test and the spec scenario).** Rejected: it is a larger change that the issue does not ask for, and the README procedure for a volume move uses the table.
- **A `nodeSelector` instead of the node affinity.** Rejected: `keeps_off_the_control_plane` reads `nodeAffinity.requiredDuringSchedulingIgnoredDuringExecution`, and the other pods use that form.
- **Merge before the volumes move.** Rejected: Argo CD tracks `main` and self-heals, and a pod with the affinity cannot start on the control-plane node while its volume is there (`k8s/README.md`, section Local-Path Volume Placement). The volumes moved before this change, so the order holds.
