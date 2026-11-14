# Design

## Decisions

**actionlint comes from the digest-pinned devcontainer image.** The fork is already pinned by digest in `.devcontainer/Dockerfile`, and its 1.17.1 binary scans clean, so the runner copies that same binary. A source build would add a Go toolchain and a stage to the runner image.

**shellcheck comes from apt.** actionlint runs shellcheck when it is on PATH, and Debian gives the package. It has no pin, like `git`, `curl` and `jq`, because a pin would fail the build on each security update.

**Trivy comes from `tools.lock`.** The image already links the lock's tools in `/opt/devops-tools/bin`, which is on PATH, so the `runner-tools` stage installs `trivy` beside `promtool`. This keeps one pin and one checksum.

**The image scan stays the gate.** No `.trivyignore` entry is added: the scan of `ci.yml` and `release.yml` must pass on the built image, and the Runner Image check runs it on the pull request.

**`HOOK_PROGRAMS` stays, with no entry.** The mechanism that leaves out a hook for a missing program remains for a future tool, but no hook needs it while the image holds actionlint.

## Rejected alternatives

- **Build actionlint from source.** It adds a Go toolchain and a build step to the runner image.
- **Download the actionlint release binary in the Dockerfile.** The Dockerfile would hold a second pin and checksum.
- **Install Trivy from apt.** Debian gives no pinned Trivy version.
- **Add a `.trivyignore` entry.** The scan is the gate that keeps the finding out, and the owner alone may lower it.
