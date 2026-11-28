# Design

## Decisions
- Add one conjunct to the non-planner branch of the pod-label validation expression in `k8s/devops/roadmap-service/admissionpolicy.yaml`:
  `(variables.stage || !("app.kubernetes.io/component" in object.spec.template.metadata.labels) || object.spec.template.metadata.labels["app.kubernetes.io/component"] != "project-review")`.
- Update the rule message to state that `app.kubernetes.io/component` is `roadmap-stage` on a stage Job pod and never `project-review` on a Service Job pod, keeping `"label"` in the message so existing rule assertions continue to match.
- Keep implement Jobs with `roadmap-implement` or with no `app.kubernetes.io/component` label admitted, and keep stage Jobs with `roadmap-stage` admitted.

## Rejected alternatives
- Allowlisting every permitted non-stage component value in CEL: rejected because each new non-stage Job component would break admission unless enumerated, whereas only `project-review` is reserved for the Argo `project-review` workflow outside `roadmap-service`.
- Adding a second `ValidatingAdmissionPolicy`: rejected because it duplicates matchConstraints and matchConditions for the same `roadmap-service` Job creation rule.
- Replacing CEL with Kyverno: rejected because `roadmap-service-jobs` already uses standard Kubernetes CEL.
