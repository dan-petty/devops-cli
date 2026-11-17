## MODIFIED Requirements

### Requirement: The planner run Job denies all egress
The stack SHALL hold a NetworkPolicy that selects the pod label `app.kubernetes.io/name: devops-cli-planner-run`, sets `policyTypes: [Egress]` and holds no egress rule. The default perimeter NetworkPolicy `devops-default-perimeter` SHALL exclude `devops-cli-planner-run` from its pod selector so that the planner run pod reaches no network.

#### Scenario: The egress rules of the planner run Job pod
- **WHEN** a test reads `k8s/devops/roadmap-service/networkpolicy-planner-run.yaml` and `k8s/devops/networkpolicy.yaml`
- **THEN** the planner policy selects the planner label, holds `Egress` and no egress rule, and `devops-default-perimeter` excludes `devops-cli-planner-run` from its pod selector
