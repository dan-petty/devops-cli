# Design

## Decisions
- Add `devops-cli-planner-run` to the `matchExpressions` of `devops-default-perimeter` with operator `NotIn`. This leaves `devops-cli-planner-run` as the single NetworkPolicy that selects the planner run pod.
- Update `check_the_planner_template_has_the_controls_of_adr_0018` in `tests/gate/k8s_checks/job_admission_policy.py` to evaluate all applied NetworkPolicies against the pod's labels and assert that exactly one policy matches.

## Rejected alternatives
- Change the planner pod label to not use `app.kubernetes.io/name`: Rejected because standard Kubernetes labels are required for stack consistency and admission control.
- Add an explicit deny egress rule in `devops-default-perimeter`: Rejected because NetworkPolicies are additive; an allow rule in another policy would still grant egress.
