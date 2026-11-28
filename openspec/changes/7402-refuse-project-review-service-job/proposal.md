# Proposal: #7402

## Why
The NetworkPolicies of `dan-petty/homelab#276` let pods with `app.kubernetes.io/name: devops-cli-job` and `app.kubernetes.io/component: project-review` in namespace `devops` connect to Prometheus (TCP 9090) and Loki (TCP 3100), and Loki has no authentication (#7402). In `k8s/devops/roadmap-service/admissionpolicy.yaml:259-268`, the ValidatingAdmissionPolicy `roadmap-service-jobs` enforces `app.kubernetes.io/component: roadmap-stage` only for stage Jobs and accepts any other component value on non-stage Service Jobs, so ServiceAccount `roadmap-service` can create a Job whose pod carries `project-review` and reads cluster logs through Loki.

## What Changes
- Extend the non-planner pod-label rule in `k8s/devops/roadmap-service/admissionpolicy.yaml` so a non-stage Service Job refuses `app.kubernetes.io/component: project-review`, while stage Jobs (`roadmap-stage`) and implement Jobs (with `roadmap-implement` or no component label) stay admitted.
- Add policy checks in `tests/gate/k8s_checks/job_admission_policy.py` verifying that a non-stage Job with `app.kubernetes.io/component: project-review` is refused and that stage and implement Jobs (with and without a component label) remain admitted.

## Capabilities
- `roadmap-implement-runner`: Refuses `app.kubernetes.io/component: project-review` on non-stage Service Job pod templates in `roadmap-service-jobs`.

## Impact
- `k8s/devops/roadmap-service/admissionpolicy.yaml`: Updates the CEL expression and refusal message of the pod-label validation rule in `roadmap-service-jobs`.
- `tests/gate/k8s_checks/job_admission_policy.py`: Adds checks for refusing `project-review` and admitting stage and implement Jobs.

## Feasibility
Verified against `k8s/devops/roadmap-service/admissionpolicy.yaml:255-270` and `tests/gate/k8s_checks/job_admission_policy.py:880-905`: the policy currently checks `variables.stage == ("app.kubernetes.io/component" in ... && ... == "roadmap-stage")` with no guard against `project-review`. Standard CEL compiles this check in `cel_expr_python` (`check_the_expressions_use_only_standard_cel`).

## Existing Tool Considered
In-use tool: Kubernetes `ValidatingAdmissionPolicy` with standard CEL (`kubernetes/kubernetes`). Adding one conjunct to the existing non-planner rule in `k8s/devops/roadmap-service/admissionpolicy.yaml` closes the gap without introducing another policy or controller, and `tests/gate/k8s_checks/job_admission_policy.py` covers the refusal check.
