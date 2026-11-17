# Design

## Decisions

### A release pin is proved by the release that runs
A pin of a chart or an image is a value that Renovate changes, so a scenario does not restate it. The rule of a pin is a floor: the release that fixes a CVE, or the first release with a feature. The live check reads, with `kubectl get`, the image tag and the `imageID` of the running pods or the image of the workload, and compares the tag with the floor and the digest with the pin. Where the rule says that the chart alone sets the image, the check compares the tag with the `appVersion` that `helm show chart` prints for the `targetRevision` of the Application. No check enters a pod with `kubectl exec`: the project forbids it for agents, because an exec into a pod near its memory limit once stopped SearXNG.

### A pin of tools.lock is proved by devops install-tools
`devops install-tools --tool <tool> --dry-run` shows the URL of the build of the host, and `install-tools status` shows the locked version. An install with `--target-dir` checks the sha256 and gives a command that prints its version. The check covers the platform of the host; each of the four platforms runs the same command.

### The layers of an image are proved by a build
#4550 measured the layers with `docker image inspect` and `docker history`. The scenarios of `container-image-layers` name these commands on two builds that differ only in the project, with the `no-cache-filters` of `ci.yml` and `release.yml`. The `lock` stage is proved by its output, which `docker buildx build --output type=local` writes.

### The devcontainer image is proved by its build and its smoke action
The `DevContainer Image` check builds `.devcontainer/Dockerfile` on a pull request that changes an image input, and `sha256sum -c`, `uv pip sync --require-hashes` and `npm ci` stop the build on a different hash. The smoke action starts the image as `vscode`. `devops install-tools status` in a container of the image shows where each command is.

### The workspace devcontainer is proved by the running container
The process limit, the GPU, the ping range, the mounts and the environment are facts of the running container: `cat /sys/fs/cgroup/pids.max`, `nvidia-smi -L`, `/proc/sys/net/ipv4/ping_group_range`, `findmnt` and `printenv` read them. `devops devcontainer validate` (the `devcontainer` row of `devops ci`) prints the base image and the count of features.

### A requirement that only restates a file goes
The key `monitoring.selfMonitoring` has no effect, because the chart does not read it. The deployment mode and its comment are a value and a comment of the values file. The guard of `--pids-limit` asked for a test that #6075 deleted. Each Migration names the requirement or the file that keeps the rule.

### A scenario that can only describe a read needs a new requirement name
OpenSpec 1.17.0 refuses a MODIFIED block that omits a scenario name of the current spec. The scenario names "The lock stage is read offline", "A test reads the lock" and "The system-package step holds the network packages" describe a read of the file. So these requirements go out as REMOVED and come back as ADDED under a new name with the same rule, as in #6120.

### The second area
The area holds the specs of the images, the release pins and the devcontainer: `loki-release-pin`, `ollama-release-pin`, `ollama-image-pin`, `cloudflared-release-pin`, `traefik-release-pin`, `tflint-release-pin`, `container-image-layers` and the `devcontainer-*` specs with a hit. No active change under `openspec/changes/` changes these capabilities. #6124 (#6119), which merged first, gave `ollama-release-pin`, `ollama-image-pin` and `traefik-release-pin` a `kubectl get` live check with no exec, so this change keeps their scenarios. #6124 also changed two requirements of `loki-release-pin`, but one scenario still said that a test reads the values, and its new deployment-mode requirement still reads the file. So this change gives the live check of the Loki image and removes the deployment-mode requirement. The requirement "The installer unpacks a zip build" of `tflint-release-pin` and "Post-create installs no locked tool" of `devcontainer-image-tools` name tests of the source code, so they stay.

## Rejected alternatives
- Keep a scenario name that describes a read of the file with new steps: the name tells the stage job to plan a test that reads the file.
- Read the version that the binary prints with `kubectl exec`: the project forbids `kubectl exec` for agents, and a later agent runs the command that a scenario names. The `imageID` of a running pod gives the digest that the node pulled, with no entry into the pod.
- Read every value of a manifest from the live object with `kubectl get -o jsonpath`: this moves the value test to the cluster. A scenario reads a live object only for the release that runs (an image tag or an `imageID`), or where no probe of the behavior exists, such as the `helm` block of Application `loki`.
- Keep the exact versions in the requirement text: Renovate changes them, and one is already stale (`loki-release-pin` says 20.0.2, and Application `loki` installs 21.2.3).
