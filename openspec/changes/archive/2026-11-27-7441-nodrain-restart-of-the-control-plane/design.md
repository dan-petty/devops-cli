# Design

## Decisions

- The stop of `_apply_alone` reads `skips_drain(planned.disruptive)`, the predicate that already chooses the cordon in place of the drain. A control-plane host stops an agent only when the apply would drain or reboot it. One predicate decides both, so the stop and the steps cannot disagree.
- The access-level check stays as it is. `apply_level` gives `full` for each disruptive class, so only an agent at `full` reaches the stop. A level check in `_apply_alone` would be a line that no public behavior reaches.
- The skip of the control-plane read comes before the read: `not nodrain and cluster.is_control_plane(...)`. A no-drain host reads no labels of its node for the stop.
- The stop at the node of the agent's own pod stays for each class. A cordon of that node and a restart of its k3s unit can stop the pod that runs the apply.

## Rejected alternatives

- Keep the stop and say in the homelab README that a person runs the server step. The owner decided on 2026-11-27 that agents run the node steps of dan-petty/homelab in a maintenance window, and only secret values, the workstation keyring, `config.yaml`, GitHub App creation and hardware stay with a person (homelab `README.md`, "Maintenance Window"). A no-drain restart is none of these.
- A new flag or setting that allows the control-plane restart. The issue asks for a rule of the level `full`, and the brief of the owner says no new flag and no config key. The level of the repo is the control.
- Allow every disruptive class on the control-plane node at `full`. A drain of the homelab server node cannot pass, because two CloudNativePG clusters with `instances: 1` run their primaries there (#6338), and a reboot takes the API server down for the whole boot. The issue keeps both with a person.
