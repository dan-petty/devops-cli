## ADDED Requirements

### Requirement: The privileged GPU workload holds a dated ignore entry
The repository SHALL hold one `misconfigurations` entry of `.trivyignore.yaml` for the rule `KSV-0017` on the path `k8s/gpu-feature-discovery/daemonset.yaml`, with a `statement` that names the privileged GPU device and sysfs access of the workload and the tracking issue #5646, and an `expired_at` date no more than 3 days after the entry.

#### Scenario: The entry of the privileged GPU workload
- **WHEN** a test reads the ignore file of the repository
- **THEN** it finds one misconfiguration entry of the rule KSV-0017 and the path of the GPU feature discovery DaemonSet, and the entry holds a statement with the tracking issue #5646 and an expiry date

#### Scenario: A second entry for another rule
- **WHEN** another judged alert adds a second misconfiguration entry to the ignore file
- **THEN** the test still finds the KSV-0017 entry of the GPU feature discovery DaemonSet and passes
