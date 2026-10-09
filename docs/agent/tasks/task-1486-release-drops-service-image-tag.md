# Task: The release no longer pins, bumps or pre-publishes the service image tag; Image Updater rolls service:latest (#1486)

**Issue**: [#1486](https://github.com/dan-petty/devops-cli/issues/1486)
**Status**: Done
**Milestone**: v0.2.32
**Priority**: priority/p2-medium
**Scope**: type/refactor, scope/release

## Description

The owner asked on 2026-10-09 to remove the custom process that updated the Service image tag. Since #1485 (v0.2.31), Argo CD Image Updater keeps Application `devops` on the digest `ghcr.io/dan-petty/devops-cli/service:latest` points at, so the pin, its bump, its check and release-branch publishing had become redundant. This item removes them and keeps building the image.

- **The cut and `release check`.** The cut no longer sets `newTag` in `k8s/devops/kustomization.yaml` or rewrites the Argo CD git sources' `targetRevision`, and `_release_paths` stages nothing under `k8s/`. `devops release check` no longer checks the pin or the `targetRevision`s: `test_git_sources_and_revisions` (`tests/test_k8s_argocd_apps.py`) already holds every git source, `bootstrap` and `cluster` included, on `main`. `CONST_SERVICE_IMAGE`, `CONST_SERVICE_IMAGE_KUSTOMIZATION` and the `updated_service_image_tag` message are gone.
- **The manifests.** `k8s/devops/kustomization.yaml` has no `images:` block. Git names the image untagged, and Image Updater's `spec.source.kustomize.images` entry on Application `devops` sets `service:latest@sha256:<digest>`.
- **`release.yml`.** It has no `release/v*` push trigger. The service-image job runs only when `github.ref == 'refs/heads/main'` (a push to `main`, or a dispatch from `main`), after the release job succeeds. It builds, smoke-tests and scans the image, pushes it by digest, attests its provenance, then tags it `vX.Y.Z` and `latest`. The plan step, `SERVICE_IMAGE_INPUTS` and the inputs label, the release-branch checks in the tag step, the promote step and the checkout's `fetch-depth: 0` (only the plan used the history) are gone.
- **`ci.yml`.** The **Service Image** job no longer skips release pull requests: it builds, smoke-tests and scans the image of every pull request into `main` without pushing it.
- **Docs.** RELEASE_CYCLE.md (the sequence diagram, Step 3 item 2, the critical-fix item 3 and Step 5 item 5), docs/ROUTINE_TASKS.md (the diagram and steps 2, 4 and 5) and k8s/README.md ("When a release merges into `main`" steps 1 and 3, "Service Image Updates" and the directory tree) describe the new flow. The task files of #1451, #741, #1261 and #755 each carry a one-line note naming what this item removed.

## Acceptance Criteria

- [x] No file in the repository and no step of the release writes or checks a Service image tag: no `images:` pin, no `newTag` bump, no pin check in `devops release check`, no `targetRevision` rewrite. `test_release_prepare_leaves_k8s_untouched` (`tests/test_release.py`) runs `devops release prepare 0.1.8` over a kustomization pinning `v0.1.7` and an Application on `release/v0.1.7`: both files stay byte-identical, and `_release_paths` names nothing under `k8s/`. `test_kustomization_lists_every_manifest_and_pins_no_image_and_stays_out_of_the_root` (`tests/test_k8s_devops_runtime.py`) holds the kustomization free of `images`, and `test_both_workloads_run_the_digest_image_updater_sets_and_pull_it_only_when_missing` still renders both workloads on Image Updater's digest without the pin.
- [x] `release.yml` runs the Service image job only on `main`, pushes it by digest, attests it and only then tags `vX.Y.Z` and `latest`, and has no release-branch trigger, plan or promote step. `test_service_image_release_job_invariants` (`tests/test_ci.py`) pins the trigger, the job's condition, needs and permissions, the absence of the plan, its gates and the promote step, the step order, the metadata tags, the push by digest with no tags and an SBOM, the tag step, the Trivy inputs, and no `${{` in a `run:` block.
- [x] `ci.yml` builds the release PR's Service image without pushing. `test_service_image_ci_job_invariants` (`tests/test_ci.py`) pins a condition with no release-branch or head-repository clause, read-only permissions, and a build that loads and does not push.
- [x] The removed tests are gone: `tests/test_release_service_image_plan.py`, the pin, bump and `targetRevision` tests in `tests/test_release.py`, `test_the_kustomization_survives_the_release_bump_rewrite` (`tests/test_k8s_devops_runtime.py`) and `test_release_service_image_inputs_are_what_the_image_is_built_from` (`tests/test_architectural_invariants.py`).
- [x] RELEASE_CYCLE.md, docs/ROUTINE_TASKS.md and k8s/README.md describe the new flow, and the #1451 task file notes it is superseded by this item.
- [x] `changelog.d/1486.md`.
- Pending a person: once this is on `release/v0.2.32`, `gh run list -R dan-petty/devops-cli --workflow release.yml --branch release/v0.2.32 --limit 3` lists no run that a push started after it.
- Pending a person: the v0.2.32 release pull request shows `ci.yml`'s **Service Image** check (build, smoke test, Trivy) green, and no **Build & Publish Service Image** check.
- Pending a person: right after the release merges, `devops argo cd apps status devops` is Synced and Healthy, and the roadmap-service pod has not restarted: `kubectl -n devops get pods -l app.kubernetes.io/name=roadmap-service -o jsonpath='{.items[*].spec.containers[*].image}'` still names the previous `service:latest@sha256:` digest.
- Pending a person: in the `release.yml` run on `main` (`gh run list -R dan-petty/devops-cli --workflow release.yml --branch main --limit 1`), the job **Build & Publish Service Image** builds, scans, pushes, attests and tags.
- Pending a person: `docker buildx imagetools inspect ghcr.io/dan-petty/devops-cli/service:latest --format '{{ .Manifest.Digest }}'` and the same for `service:v0.2.32` print the same digest, and `gh attestation verify oci://ghcr.io/dan-petty/devops-cli/service:v0.2.32 -R dan-petty/devops-cli --signer-workflow dan-petty/devops-cli/.github/workflows/release.yml --source-ref refs/heads/main` passes.
- Pending a person: within about two minutes, `kubectl -n argocd get imageupdater devops -o jsonpath='{.status.recentUpdates}'` records that digest, `kubectl -n argocd get application devops -o jsonpath='{.spec.source.kustomize.images}'` holds it, and the roadmap-service pod's `imageID` (`kubectl -n devops get pods -l app.kubernetes.io/name=roadmap-service -o jsonpath='{.items[*].status.containerStatuses[*].imageID}'`) and CronJob `devops-cli`'s image (`kubectl -n devops get cronjob devops-cli -o jsonpath='{.spec.jobTemplate.spec.template.spec.containers[*].image}'`) carry it.
- Pending a person: `git log origin/main -- k8s/devops/kustomization.yaml` shows no commit after the release merge.

## Decisions and Deviations

- **The job runs only when `github.ref` is `refs/heads/main`.** One clause covers a push to `main` and a dispatch from `main`, and `success()` of `needs: release` is implied. A dispatch from another branch, or a tag push, runs the release job but publishes no Service image, so nothing but `main` moves `latest`, which Image Updater deploys within one poll.
- **Every run on `main` rebuilds the image and moves both tags.** `release.yml` runs on every push to `main`, and its release job already re-publishes the GitHub Release and the devcontainer's `vX.Y.Z,latest` each time. A later push, such as one that recovers a failed release run, builds the image from `main`'s tree, moves `vX.Y.Z` and `latest`, and Image Updater rolls the workloads onto it. No guard was added.
- **A dispatch's `version` input names the image.** The image takes the version the GitHub Release takes, `needs.release.outputs.version`; the plan's check that the tree holds that version is gone, and no guard replaces it.
- **A re-created Application renders the untagged image.** Until Image Updater's next poll writes the digest again, a re-created `devops` Application renders `ghcr.io/dan-petty/devops-cli/service` with no tag (`latest`); with `imagePullPolicy: IfNotPresent` a node pulls it only when it holds no copy.
- **The merge's own sync restarts nothing.** Image Updater's `kustomize.images` entry already outranked the pin, so removing the pin leaves the rendered image, `service:latest@sha256:<digest>`, unchanged until `latest` moves.
- **Release pull requests no longer need `main` merged in for the image.** The plan step compared the release branch's image inputs with the merge of `main`; `ci.yml` builds the pull request's merge commit, and `release.yml` builds `main`'s tree, so neither needs it.
- **#755's task file got a note too.** It still described the cut rewriting `targetRevision`, which this item removes, so it carries a one-line note like those of #1451, #741 and #1261. #1485's task file already scopes the pin "until #1486" and stays as it is.

## Deliverables

- [x] `src/devops_cli/commands/release.py`: the pin, bump, `targetRevision` rewrite and their checks removed; `_release_paths` stages nothing under `k8s/`.
- [x] `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`: the service-image constants and message removed.
- [x] `k8s/devops/kustomization.yaml`: the `images:` block removed.
- [x] `.github/workflows/release.yml`, `.github/workflows/ci.yml`.
- [x] `tests/test_release.py`, `tests/test_ci.py`, `tests/test_k8s_devops_runtime.py`, `tests/test_architectural_invariants.py`; `tests/test_release_service_image_plan.py` deleted.
- [x] RELEASE_CYCLE.md, docs/ROUTINE_TASKS.md, k8s/README.md.
- [x] Notes in the task files of #1451, #741, #1261 and #755.
- [x] `changelog.d/1486.md`.
