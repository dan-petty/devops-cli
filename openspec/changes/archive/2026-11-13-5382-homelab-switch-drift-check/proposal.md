# Proposal: #5382

## Why

Step 10 of `docs/HOMELAB_REPO_SWITCH.md` has 2 errors, which the review of dan-petty/homelab#23 found (#5382):

1. The drift check runs `git diff --stat <S> origin/main -- <environment-paths>` with the path list of the metadata file of the homelab copy. That path list holds only the files at S, so the diff does not show a new environment file that devops-cli adds after S. devops-cli has no copy of the path list, and `git diff` with no path after `--` compares the full repository.
2. Step 10.3 says to run the checks of dan-petty/homelab#23 again. These checks include `argocd app diff <app> --core --local <folder>`. That command runs `kustomize edit` in the folder and writes the live overrides of the Application, which hold the real hosts, into the `kustomization.yaml` files. A commit of such a checkout puts the hosts in git.

Closes #5382.

## What Changes

- Step 10.2 compares the environment files with the pathspec of the sync: `k8s ':(exclude)k8s/devops' ':(exclude)k8s/overlays/homelab/devops'`. It says why the path list of the metadata file is not correct for the check.
- Step 10.3 runs `argocd app diff --local` only on a throwaway export (`git archive HEAD | tar -x`) of a committed sync, and deletes the export after the diff.
- The check of step 10 adds 2 items: the homelab checkout has no change, and the export does not exist.

The change alters only a document, so it has no spec delta (`skip_specs: true`). The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. No spec holds the steps of the runbook.

## Impact

- `docs/HOMELAB_REPO_SWITCH.md`, step 10. No code, manifest or test changes.
- The pre-checks of plan step 10 in the body of #5134 hold the same drift command. The body of an issue is not in git, so this pull request does not change it.

## Feasibility

Checked on 2026-11-13 against origin/main (v0.127.0), git 2.55.0 and the Argo CD source at v3.6.1 (the version of `src/devops_cli/tools_lock/tools.lock`):

- Path list against pathspec, with S = v0.120.0 in devops-cli: the files of `k8s` without the 2 product folders at S are 133. From S to origin/main, a diff with the path list of S shows 17 changed files, and a diff with the pathspec shows 20. The 3 extra files are environment files that devops-cli added after S. A diff with no path after `--` shows 910 files. The pathspec diff holds 0 files of the 2 product folders.
- `git ls-tree` refuses the `exclude` magic ("pathspec magic not supported by this command"), so the runbook uses the pathspec only with `git diff`.
- dan-petty/homelab#23 (pull request dan-petty/homelab#39, README section "Sync the Copy Again") uses the same pathspec, and the same throwaway export for `argocd app diff --local`.
- `cmd/argocd/commands/app_diff.go` (`getLocalObjectsString`) calls `repository.GenerateManifests` on the `--local` folder with the source of the live Application. `util/kustomize/kustomize.go` (`Build`) then runs `kustomize edit set image` and the other `kustomize edit` commands in that folder, and writes the patches of the Application into `kustomization.yaml` with `os.WriteFile`. The issue records the result of one run: 14 lines in `k8s/mattermost/kustomization.yaml` and 162 lines in `k8s/overlays/homelab/ingress/kustomization.yaml` of a scratch copy.
- `git archive HEAD | tar -x -C <dir>` with GNU tar 1.35 writes the files of the commit and no `.git` folder. The homelab repository has no `.gitattributes`, so no `export-ignore` removes a file from the export.

## Existing Tool Considered

git pathspecs (`:(exclude)` magic) and `git archive`. The change adds no code and deletes no code.
