## REMOVED Requirements

### Requirement: The roadmap configuration holds only the board
**Reason**: The roadmap jobs read no project board (#2399), and `board` was the file's one key. `.github/roadmap.toml` and its reader are deleted.
**Migration**: Delete `.github/roadmap.toml` from each managed repository. The requirement "No roadmap job reads or writes a project board" of `roadmap-item-labels` holds the rule.
