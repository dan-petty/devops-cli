# Design

## Decisions

### Renew KSV-0017 for 3 days per SECURITY.md
SECURITY.md states that an agent judges an alert below CRITICAL with an ignore entry of 3 days, up to 14 days total.
The workload requires `privileged: true` until #5646 delivers a non-privileged manifest.
Renew the entry through 2026-11-26.

### Renew companion entries on the GPU DaemonSet
The rules KSV-0121 and KSV-0118 apply to the same DaemonSet and expired on 2026-11-21.
Renew them together with KSV-0017 to 2026-11-26.

### Keep the tracking issue reference
The statement references tracking issue #5646 and names the requirement for privileged GPU device and sysfs access.

## Rejected alternatives

- **Set 90 days**: Only the repository owner can approve an ignore longer than 14 days. An agent follows the 3-day renewal limit.
- **Remove privileged mode now**: Removing `privileged: true` breaks GPU device discovery on the node.
- **Dismiss the alert**: An agent does not dismiss alerts in code scanning; a person must do so if appropriate.
