# Design

## Decisions

- **Delete, not archive.** An archive applies the delta specifications of a change to `openspec/specs/`. The plans of #4530, #4600, #2144, #2526, #3236 and #3485 were not built, so their requirements must not go into the specifications. The delivered change of #3060 is archived already; the active folder is a copy that later refactors of the folder layout changed.
- **Only the folders whose state needs no check of the code.** An issue that left the repository, an issue that is closed as not planned, and a folder with an archived twin are clear from GitHub and from the tree.
- **No change of the stage Job.** #7337 makes the read of an issue that left the repository safe. This change removes the input that makes the read fail.

## Rejected alternatives

- **Remove the 5 folders of issues that are closed as completed with no archived change (#1327, #2176, #3077, #3447, #3782) in the same pull request.** Each needs a check of what was delivered before an archive or a deletion, so they stay for a follow-up item.
- **Move the plans of #4530 and #4600 to the repository that holds the items now.** Those plans name files that this repository deleted, and that repository plans its items with its own change folders.
