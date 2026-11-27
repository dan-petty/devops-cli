# Tasks

## 1. Delete the change folders of items that are gone

Kind: other

Changes: `openspec/changes/4530-expose-the-argo-workflows-ui-behind/`, `openspec/changes/4600-list-each-service-ui-on-the/`, `openspec/changes/2144-add-scheduled-off-node-backup-and/`, `openspec/changes/2526-the-five-defect-fixes-merged-on/`, `openspec/changes/3236-read-only-tools-take-paths-that/`, `openspec/changes/3485-the-coder-tier-serves-no-second/`, `openspec/changes/3060-a-model-ladder-for-retries-with/`.

- [x] 1.1 Delete the 7 folders with `git rm -r`.
  - Verification: `$ ! git grep -q -e . -- openspec/changes/4530-expose-the-argo-workflows-ui-behind openspec/changes/4600-list-each-service-ui-on-the openspec/changes/2144-add-scheduled-off-node-backup-and openspec/changes/2526-the-five-defect-fixes-merged-on openspec/changes/3236-read-only-tools-take-paths-that openspec/changes/3485-the-coder-tier-serves-no-second openspec/changes/3060-a-model-ladder-for-retries-with`
- [x] 1.2 Check that the change folders and the specifications stay valid.
  - Verification: `$ uv run devops ci --check --only openspec,docs`

## Workflow follow-up

- The folders of #1327, #2176, #3077, #3447 and #3782 (issues closed as completed, no archived change) need a check of what was delivered; a follow-up item settles them.
- The plan of #4576 stays with #7323.
