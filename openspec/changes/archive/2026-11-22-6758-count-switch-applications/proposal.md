# Proposal: #6758

## Why

`docs/HOMELAB_REPO_SWITCH.md` gives fixed counts of Applications in its rules and steps: "31 of the 34 Applications" (line 15), "the 32 child Applications" (lines 158 and 201) and "all 34 Applications" (lines 164, 170, 206, 230, 285 and 302). Argo CD now has 36 Applications, because #4750 and #6724 added `seaweedfs-operator` and `object-store`. dan-petty/homelab#99 copies the environment again, and each new Application makes the fixed counts false again (#6758).

## What Changes

- The steps of `docs/HOMELAB_REPO_SWITCH.md` name the Applications by their source, not by a number: "each Application of the copy" (the list `applications` of `k8s/devops-cli-copy.json` in homelab) and "each child Application of `cluster`".
- The rule about the finalizer `resources-finalizer.argocd.argoproj.io` gives no count, and it points to the dated baselines of step 10.
- Step 10 keeps the dated baseline of 2026-11-13, with the finalizer count of 2026-11-12 from the rule, and adds the dated baseline of 2026-11-22: 36 Applications, 34 Synced and Healthy, 2 Synced and Progressing, `requiresPruning` only on `argocd` (3 objects), and 33 of the 36 Applications with the finalizer. `argocd`, `bootstrap` and `cluster` have no finalizer.
- The change alters only a document. No behavior that a consumer observes changes, so the change carries no spec delta and sets `skip_specs: true`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. The change edits a runbook only, so it carries no spec delta.

## Impact

- Documents: `docs/HOMELAB_REPO_SWITCH.md`

## Feasibility

- The premise holds at main a3e30286e on 2026-11-22. `grep -n -E '\b3[1-6]\b' docs/HOMELAB_REPO_SWITCH.md` finds the counts at lines 15, 122, 158, 164, 170, 201, 206, 230, 285 and 302. Line 122 is the dated baseline of 2026-11-13.
- Read-only `kubectl -n argocd get applications -o json` with `jq` gave 36 Applications, 34 `Synced/Healthy` and 2 `Synced/Progressing`, `requiresPruning` only on `argocd` (3 objects), and the finalizer on 33 of the 36. `argocd`, `bootstrap` and `cluster` have no finalizer.
- `k8s/devops-cli-copy.json` on homelab `main` has the keys `applications`, `checksums`, `commit`, `paths`, `release`, `release_commit`, `renders` and `source`. `applications` is a list of names that holds `argocd`, `bootstrap` and `cluster`. It holds 34 names, because dan-petty/homelab#99 is still open. So a count from that list is correct after each copy, and a fixed number is not.
- `git grep` for "34 Applications", "32 child" and "31 of" finds no other document, spec or test with these counts. The only other Application count is in an eval fixture (`tests/fixtures/roadmap_eval/implement/2579-argo-sources-tests/issue.md`), which records an issue of 2026-10-29 as it was, so it stays.

## Existing Tool Considered

The change needs no tool. The list `applications` of the homelab metadata file already names the Applications of the copy, and shared checks 1 and 5 of the runbook count the live Applications. The change deletes no internal code. The written cost is about 3,000 tokens and about 15 minutes.

## Dependencies

- #4750 and #6724 added `seaweedfs-operator` and `object-store`, done.
- dan-petty/homelab#99 copies the environment again with 36 Applications, open. The change does not wait for it, because the steps name the list and not a number.
