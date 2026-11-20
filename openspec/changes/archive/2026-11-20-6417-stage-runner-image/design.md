# Design

## Decisions

- **One image rule for every Job of the Service.** The implement, fix-checks, planner run and stage Jobs all run the runner image, so the rule has no branch for a stage Job. The other rules of a stage Job stay.
- **The template `roadmap-stage` stays.** Its deadline, retries, pod failure policy, resources, plain environment, component label and SearXNG egress differ from the runner template, and the policy and the Service key on them.
- **No change to the resources, the volumes or the user.** The pod runs the same Python process. The runner image has the same user (1000:1000), `HOME` (`/home/devops`) and writable paths as the Service image, and the pod already mounts `emptyDir` volumes on them. The image size changes the pull time, not the memory of the process. The first stage Job after the sync measures the memory again.
- **No bootstrap and no shell.** The stage Job starts only `git`, `gh` and `openspec` of the image. #6528 runs stage as a `Coder` agent with a shell and the bootstrap of the checkout.
- **No new ImageUpdater entry.** The entry `runner` writes `ghcr.io/dan-petty/devops-cli/runner:latest@<digest>` into `spec.source.kustomize.images` of Application `devops`, and kustomize sets that digest on each container that names the image, also in a CronJob.

## Rejected alternatives

- **Admit both images for a stage Job.** The policy would then admit a stage Job in the Service image, which the owner decision of 2026-11-19 removes.
- **Merge `roadmap-stage` into `devops-cli-runner`.** The two Jobs differ in the rules above, and the Service selects a stage Job by its name and its component label.
- **Run the bootstrap of the checkout in the stage Job now.** The stage code starts no tool of its checkout, so a bootstrap adds time and gives the Job nothing until #6528.
- **Raise the memory of the stage pod.** No measurement shows a need: the Service pod, which ran every row, peaked at 1.46 GiB. The policy pins the 4 values, so a change after a measurement changes both.
- **OpenSpec of the project pin in the stage Job.** The stage Job runs the OpenSpec of the devtools image, 2.1.0 on 2026-11-20, which equals the pin of `package-lock.json`. The pin reaches a Job only through the bootstrap (#6409, #6517), which #6528 adds.
