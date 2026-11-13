## ADDED Requirements

### Requirement: RuntimeClass gvisor declares the measured pod overhead
RuntimeClass `gvisor` in `k8s/runtimeclass-gvisor.yaml` SHALL declare `overhead.podFixed` with a `memory` value from a measurement of `runc` against `runsc` on a labelled node, rounded up to a whole MiB. The measurement of #5434 gave 15.1 MiB, so the value SHALL be `16Mi`. The class MUST NOT declare a `cpu` overhead, because the measurement found no CPU overhead.

#### Scenario: The class declares only the measured memory overhead
- **WHEN** a test reads the `overhead` of RuntimeClass `gvisor` in `k8s/runtimeclass-gvisor.yaml`
- **THEN** it is exactly `podFixed: {memory: 16Mi}`, with no `cpu` key
