# Design

## Decisions

- **The installed modules give the failure classes, the runner tools and `NOT_IN_RUNNER`.** The runner image is the devops-cli image for every repository, so these facts do not depend on the commit of the target. The stage already imports both modules (`stage_change.py` imports `NOT_IN_RUNNER`, and `stage.py` imports `FailureClass`), so the change adds no dependency.
- **`runner_tools.py` in the staged commit marks a devops-cli commit.** Only a devops-cli commit holds that path. The builder reads the `Dockerfile` and `k8s/devops/cronjob-runner.yaml` only for such a commit, and it leaves out each fact whose file the commit lacks.
- **A test holds the 3 paths of the staged facts.** `runner_tools.py`, the `Dockerfile` and the pod manifest must exist in the repository. A move then fails the pull request that makes it (AGENTS.md rule 11), and the Job never meets it.
- **Each `NOT_IN_RUNNER` line holds its reason text.** The installed dict holds the resolved text. The old ast extractor wrote the name of a constant for 22 of 28 entries, and that name is not a fact that the planner can use.
- **The trigger patterns stay.** The fix changes where the facts come from, not which items get them.
- **The stage eval keeps `facts_source`.** A golden case is frozen at an old commit that can lack `runner_tools.py` or a runner file. The fallback to the checkout keeps the image facts of the case.

## Rejected alternatives

- **Gate the image facts on the presence of `Dockerfile` and the pod manifest.** Rejected: a target repository can hold a Dockerfile for its own image. The stage would then state a wrong fact about the runner image.
- **Keep the raise when a devops-cli commit lacks the `Dockerfile` or the pod manifest.** Rejected: the issue asks for no raise, and the test of the 3 paths fails the pull request that moves a file. A raise in the Job would stop the stage for a fault that CI already catches.
- **Keep the text byte-equal by an ast parse of the installed source.** Rejected: the 22 base lines hold the name of a constant. To keep them, the builder would parse the source again to write a name that is not a fact. The diff of the base and new text shows that only those 22 lines change.
- **Add a setting that names the repository kind.** Rejected: the module path already tells the fact, and the runner image is the same for every repository.
- **Store the devops-cli text as a syrupy snapshot.** Rejected: the text holds the real `NOT_IN_RUNNER`, `FailureClass`, Dockerfile and pod manifest values, and `failure.py` changed in 19 commits in the last 30 days. Each change would update the snapshot and not find a defect. The tests assert each fact that the section must hold.
