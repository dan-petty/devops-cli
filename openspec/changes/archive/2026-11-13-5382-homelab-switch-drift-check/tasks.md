# Tasks

## 1. Documents

- [x] 1.1 Step 10.2 of `docs/HOMELAB_REPO_SWITCH.md` compares the environment files with the `k8s` pathspec and the 2 product exclusions, not with the path list of the metadata file
  - Verification: `$ grep -q -F -e "-- k8s ':(exclude)k8s/devops' ':(exclude)k8s/overlays/homelab/devops'" docs/HOMELAB_REPO_SWITCH.md`
- [x] 1.2 Step 10.3 runs `argocd app diff --local` only on a throwaway export of a commit, and deletes the export after the diff
  - Verification: `$ grep -q -F "archive HEAD | tar -x -C <temp-dir>/export" docs/HOMELAB_REPO_SWITCH.md`
- [x] 1.3 No step of the runbook names the path list placeholder `<environment-paths>`
  - Verification: `$ ! git grep -n -F environment-paths -- docs/HOMELAB_REPO_SWITCH.md`
