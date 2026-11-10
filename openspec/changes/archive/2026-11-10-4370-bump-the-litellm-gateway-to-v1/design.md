# Design

## Decisions

- **The 1.103 line, release 10.** It is the smallest step that holds both fixes: it keeps the minor line, so the only changes are patch backports. A minor update to 1.104 to 1.108 adds a larger set of changes for no further advisory fix that this repository needs.
- **A tag and no digest.** The manifests of the repository pin the image by tag. Renovate pins digests for GitHub Actions only. The digest of the tag was read from the registry and is in the pull request comment for the check after the merge.
- **A guard test.** `GATEWAY_ADVISORY_FIXED_IN` lists the first fixed release of each line. The test fails when the pin is below it. A pin on a line that is not in the table fails unless it is newer than the newest line of the table.
- **The text of the cost map follows the new map.** The comment in `config.yaml` and the paragraph in the README said that the pinned map lists no Claude 5.5 model. The map of v1.103.10 lists both, so the text names the facts as merged. The Claude groups keep their own prices and their own `additional_drop_params`.

## Rejected alternatives

- **Version 1.108.4, the latest.** Rejected: five minor lines of changes, and a release from the day before the change. The 1.103 line has both fixes.
- **Version 1.105.0, the earlier proposal.** Rejected: it does not hold the second fix (1.105.6), and a person left it for a later decision.
- **Set `EXPERIMENTAL_UI_LOGIN=false` as the mitigation.** Rejected: the advisory names it only as a mitigation when an upgrade is not possible, and the upgrade is.
