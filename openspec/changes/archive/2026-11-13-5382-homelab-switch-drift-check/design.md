# Design

## Decisions

- The drift check uses the pathspec of the sync of the homelab copy: `k8s ':(exclude)k8s/devops' ':(exclude)k8s/overlays/homelab/devops'`. The README of the homelab copy uses the same pathspec, so the runbook and the sync compare the same set of files. A pathspec selects files by folder, so a new environment file in `k8s` shows in the diff.
- The second command of step 10.2, `git diff --quiet <vX> origin/main -- k8s/devops/dashboards`, does not change. The copy reads the dashboards from the release vX, and the pathspec excludes `k8s/devops`.
- `argocd app diff --local` runs on a throwaway export in `<temp-dir>`: `git -C <homelab-checkout> archive HEAD | tar -x -C <temp-dir>/export`. The export holds no `.git` folder, so a person or an agent cannot commit the overrides that the diff writes. `git archive` reads a commit, so the step says to commit the sync first. The step deletes the export after the diff, because the export then holds the real hosts.
- The check of step 10 reads the result of the rule: `git -C <homelab-checkout> status --porcelain` prints nothing, and `<temp-dir>/export` does not exist.

## Rejected alternatives

- Keep the path list of the metadata file and add the new files by hand. Rejected: the path list holds only the files at S. With S = v0.120.0, the path list misses 3 environment files that devops-cli added after S (17 changed files against 20 with the pathspec).
- Read the path list from the metadata file in devops-cli. Rejected: the metadata file is in the homelab repository only. With no path after `--`, `git diff` compares the full repository (910 files from v0.120.0).
- Run `argocd app diff --local` on the checkout and run `git checkout -- .` after it. Rejected: the hosts are on disk until the restore, and a missed restore or a commit before it puts the hosts in git.
- Run `argocd app diff` without `--local`. Rejected: that diff reads the source of the live Application, which is devops-cli before the switch, so it does not check the files of the homelab copy.
