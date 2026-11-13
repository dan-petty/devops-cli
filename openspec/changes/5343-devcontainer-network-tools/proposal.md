# Proposal: #5343

## Why

The devcontainer image has no basic network diagnostics tools (#5343). `dig`, `nslookup`, `ip`, `ss` and `curl` are in the image, but `ping`, `tracepath`, `traceroute`, `mtr`, `nc` and `tcpdump` are not. So a person cannot find the cause of a network fault from the container.

## What Changes

- The system-package step of `.devcontainer/Dockerfile` installs the Debian packages `iputils-ping`, `iputils-tracepath`, `traceroute`, `mtr-tiny`, `netcat-openbsd` and `tcpdump`. The step adds no `dnsutils`, because a feature of the image configuration installs `dig` and `nslookup` already.
- `runArgs` of `.devcontainer/devcontainer.json` and of `src/devops_cli/templates/devcontainer.json.j2` add `--sysctl=net.ipv4.ping_group_range=1000 1000`. Then the user `vscode` can open an ICMP echo socket, and `ping` works with no `sudo`. The value replaces the `0 0` that Podman sets.
- `mtr` works with no `sudo`, because the `mtr-tiny` package gives `mtr-packet` the `cap_net_raw` file capability. `tcpdump` needs `sudo`.
- `tests/invariants/test_devcontainer_config.py` fails when the system-package step has no network package, when `runArgs` has no such sysctl, or when the run arguments of a scaffolded devcontainer are not those of the workspace.
- `docs/DEVCONTAINER_USAGE.md` lists the tools and their limits, and `CONTRIBUTING.md` names the run argument and the rebuild.
- The change has a spec delta, because a person in the container sees the tools and the run argument: two ADDED requirements of `devcontainer-image-tools`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `devcontainer-image-tools`: The image installs the network diagnostics tools, and the user `vscode` can open an ICMP echo socket.

## Impact

- Image: `.devcontainer/Dockerfile`. The new packages pull `systemd` into the system-package step. The image has `systemd` already, because `openssh-client` of the common-utils feature has the same dependency.
- Configuration: `.devcontainer/devcontainer.json`, `src/devops_cli/templates/devcontainer.json.j2`
- Tests: `tests/invariants/test_devcontainer_config.py`
- Documents: `docs/DEVCONTAINER_USAGE.md`, `CONTRIBUTING.md`
- A person must rebuild the devcontainer after the release publishes the image. No CI runner changes. The DevContainer Image job builds the image, and its smoke test writes its own configuration with no `runArgs`.

## Feasibility

- The running devcontainer (rootless Podman, `keep-id`, image of 2026-11-12) has `dig`, `nslookup`, `ip`, `ss` and `curl`, and `command -v` finds no `ping`, `tracepath`, `traceroute`, `mtr`, `nc` or `tcpdump`. `/var/log/apt/history.log` shows that the feature step `apt-get install -y iptables ipset dnsutils jq curl aggregate` installed `bind9-dnsutils` 1:9.20.30-1.
- `apt-cache show` on the pinned `debian:sid` image gives `iputils-ping` 3:20250605-1, `iputils-tracepath` 3:20250605-1, `traceroute` 1:2.1.6-1, `mtr-tiny` 0.96-2+b1, `netcat-openbsd` 1.239-1 and `tcpdump` 4.99.7-1. `iputils-ping` has no postinst and recommends `linux-sysctl-defaults`, so Debian gives `ping` no file capability and expects `net.ipv4.ping_group_range`. The postinst of `mtr-tiny` runs `setcap cap_net_raw+ep /usr/bin/mtr-packet` when `setcap` is installed. The system-package step installs `libcap2-bin` as a dependency, so `getcap` in a test image of the step shows `cap_net_raw=ep` on `mtr-packet`.
- The `containers.conf` of containers/common sets `default_sysctls = ["net.ipv4.ping_group_range=0 0"]`, and its default capabilities have no `NET_RAW`. The running container shows `0 0`. The docker-in-docker feature runs the container privileged: PID 1 has every capability, the user `vscode` has none in effect and a full bounding set, `NoNewPrivs` is 0, and `sudo` asks no password.
- A Python probe in the running container as `vscode` gets `EACCES` for an ICMP echo socket and `EPERM` for a raw socket and a packet socket. As root through `sudo`, all three sockets open, and an ICMP echo gets a reply from a public address.
- The kernel reads the bounds of `ping_group_range` in the user namespace that owns the network namespace, and refuses a bound that the namespace does not map. Moby (`daemon/oci_linux.go`) sets `0 2147483647` only when the daemon is not in a user namespace, with the comment "We cannot set up ping socket support in a user namespace". A nested Docker in the running container has the same user namespace. There, `0 2147483647` and `0 65537` stop the container at its start, and `0 65536` starts the container but `ping` as uid 1000 fails. `1000 1000` and `1000 65536` let `ping` work as uid 1000. So the value of the issue cannot be used, and the change uses `1000 1000`.
- A file capability of the image works for uid 1000 under rootless Podman with `keep-id`: `gst-ptp-helper` of `libgstreamer1.0-0` runs with `CapEff` `cap_net_bind_service,cap_net_admin,cap_sys_nice`. So `mtr-packet` gets `cap_net_raw` in the built image.
- A test image of the pinned `debian:sid` with the new system-package step, privileged, run as uid 1000 with `--sysctl net.ipv4.ping_group_range=1000 1000`: `ping -c 1`, `tracepath -n`, `traceroute -n`, `mtr --report -c 1` and `nc -zv -w 5 github.com 443` pass. `tcpdump -c 1` as uid 1000 fails to open a packet socket, and as root it captures a packet.
- Pasta connects the running container to the network. UDP probes with a TTL of 1 to 5 get an ICMP "time exceeded" from each hop. An ICMP echo with a TTL of 1, 2 or 3 gets an echo reply from the destination. So `tracepath` and `traceroute` show each hop, and `mtr` and `traceroute -I` show only the destination. The document states this limit.

## Existing Tool Considered

The change uses the Debian packages `iputils-ping`, `iputils-tracepath`, `traceroute`, `mtr-tiny`, `netcat-openbsd` and `tcpdump`, and the standard `--sysctl` option of `podman run` and `docker run`. It builds no code of its own, and deletes no internal code. The cost is six package names, one run argument in two files, two tests and two document paragraphs.
