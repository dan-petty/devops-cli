## ADDED Requirements

### Requirement: The default pod security context of the GPU workload holds a dated ignore entry
The repository SHALL hold one `misconfigurations` entry of `.trivyignore.yaml` for the rule `KSV-0118` on the path `k8s/gpu-feature-discovery/daemonset.yaml`, with a `statement` that names the default pod security context of the workload and the tracking issue #5646, and an `expired_at` date no more than 3 days after the entry.

#### Scenario: The entry of the default pod security context
- **WHEN** a test reads the ignore file of the repository
- **THEN** it finds one misconfiguration entry of the rule KSV-0118 and the path of the GPU feature discovery DaemonSet, and the entry holds a statement with the tracking issue #5646 and an expiry date

#### Scenario: Existing entries for other rules
- **WHEN** another judged alert adds or keeps other misconfiguration entries in the ignore file
- **THEN** the test still finds the KSV-0118 entry of the GPU feature discovery DaemonSet and passes
