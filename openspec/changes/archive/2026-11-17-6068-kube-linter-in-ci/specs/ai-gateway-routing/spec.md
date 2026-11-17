## ADDED Requirements

### Requirement: A rendered tier keeps the annotations of its template that control no render
The render SHALL drop the annotations `llm.devops.io/gpu-count` and `llm.devops.io/embedding-model` of a tier template, which control the render, and SHALL keep each other annotation of the template on each tier that it writes, such as the reason of a kube-linter exception.

#### Scenario: A template with a kube-linter exception
- **WHEN** a tier template holds the two control annotations and the annotation `ignore-check.kube-linter.io/run-as-non-root`, and the render writes it at both thresholds or above both
- **THEN** each tier that the render writes holds only the annotation `ignore-check.kube-linter.io/run-as-non-root`
