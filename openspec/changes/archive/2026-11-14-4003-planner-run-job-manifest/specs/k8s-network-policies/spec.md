## ADDED Requirements

### Requirement: The planner run Job denies all egress
The stack SHALL hold a NetworkPolicy that selects the pod label `app.kubernetes.io/name: devops-cli-planner-run`, sets `policyTypes: [Egress]` and holds no egress rule.

#### Scenario: The egress rules of the planner run Job pod
- **WHEN** a test reads `k8s/devops/roadmap-service/networkpolicy-planner-run.yaml`
- **THEN** the policy selects the planner label, holds `Egress` and no egress rule
