# Design

## Decisions
- **Two volumes for the run folder.**: `make_out` refuses an `out/` that is there before the outputs, so `out/` cannot be a mount point. The run root is one volume, and `state/` is a second volume on top of it that `agent` does not mount.
- **One path for the run root in each container.**: `prepare` records the absolute path of the clone, and `agent` opens it, so each container mounts `run` at `/run/roadmap`.
- **Each container has its own tmp and home.**: `publish` makes its new repository in a temporary folder of its own, and no writable volume of `agent` reaches `publish`.
- **The policy pins the mounts and their paths.**: a `state` mounted elsewhere in `publish` would leave the empty folder of the run root in its place, which `agent` can write.
- **The one-container shape stays only for an UPDATE.**: the Service patches the deadline of a Job that runs, and a Job keeps its pod template.
- **Sync wave `-1`.**: the policy and the CronJob are in one Application, so the wave orders them.

## Rejected alternatives
- **Share one volume for the run folder and the state.**: Rejected: `agent` could then read and write the state file.
- **A shared home for the three containers.**: Rejected: `agent` could write a file that `publish` reads later, such as a git configuration.
- **Admit the old shape on a CREATE during the switch.**: Rejected: the criteria ask for the one-container shape on an UPDATE only, and the wave makes the gap short.
