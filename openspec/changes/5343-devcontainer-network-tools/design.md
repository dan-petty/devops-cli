# Design

## Decisions

- **Install the six packages in the system-package step of the last stage.**: That step installs the other Debian packages of the image. Like them, the new packages have no version pin: the digest of `debian:sid` pins the base, and each image build takes the current packages.
- **Set `--sysctl=net.ipv4.ping_group_range=1000 1000`.**: Debian's `ping` opens an ICMP echo socket and has no file capability, and only a group in the range can open that socket. Under rootless Podman with `keep-id`, the kernel compares host group IDs, and gid 1000 of `vscode` maps to a host ID below the host IDs of every other group of the container. So a range that holds gid 1000 starts at 1000. The range holds only the group of `vscode`, which is the least grant that lets `vscode` run `ping`. Root keeps `ping`, because the container is privileged and root has `CAP_NET_RAW`, so `ping` uses a raw socket for root.
- **Give the scaffolded devcontainer the same run arguments.**: `devops devcontainer init --published` writes a configuration of the same image. Without the run argument, `ping` of that image fails for `vscode`. The test compares the two `runArgs` lists, so they cannot drift.
- **Add no `--cap-add=NET_RAW`.**: The docker-in-docker feature runs the container privileged, and the bounding set of `vscode` has every capability already. A capability in the bounding set has no effect for a non-root user without a file capability.
- **Keep `tcpdump` behind `sudo`.**: A packet socket can read all traffic of the container. A file capability on `tcpdump` gives that right to every user of the container. `vscode` has `sudo`, so the document says `sudo tcpdump`.
- **Let `tcpdump` pull `systemd` into the step.**: `tcpdump` depends on `systemd | systemd-standalone-sysusers | systemd-sysusers`. `openssh-client` of the common-utils feature has the same dependency and installs `systemd` in the image today, so `systemd` is not new in the final image.
- **Add no `dnsutils`.**: A feature step installs `bind9-dnsutils`, so `dig` and `nslookup` are in the image.
- **Put the guards in `tests/invariants/test_devcontainer_config.py`.**: The module reads the committed files of `.devcontainer/` already.

## Rejected alternatives

- **`--sysctl=net.ipv4.ping_group_range=0 2147483647`, the value of the issue.**: The user namespace of rootless Podman maps no gid 2147483647, so the kernel refuses the value and the container does not start. A nested Docker in the running container refused it, and Moby sets this value only outside a user namespace.
- **`--sysctl=net.ipv4.ping_group_range=0 65536`.**: The container starts, but `ping` as uid 1000 fails, because the host ID of gid 1000 is below the host ID of gid 0. A nested Docker test showed the failure.
- **`--cap-add=NET_RAW`.**: It changes nothing in a privileged container, and it gives no capability to a non-root user.
- **A `cap_net_raw` file capability on `ping`.**: Debian removed it and uses `ping_group_range` instead. A raw socket is a wider right than an ICMP echo socket.
- **Only `sudo ping`.**: The issue asks for `ping` as `vscode` with no `sudo`.
- **Add `systemd-standalone-sysusers` to keep `systemd` out of the step.**: It also satisfies the dependency of `openssh-client`, so the final image would lose `systemd`. That change is out of the scope of the issue.
