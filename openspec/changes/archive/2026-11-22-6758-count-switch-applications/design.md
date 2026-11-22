# Design

## Decisions

- **Name the source of the Applications, not a number.**: The steps say "each Application of the copy" and "each child Application of `cluster`". The list `applications` of `k8s/devops-cli-copy.json` in homelab names the Applications of the copy, and each new copy writes it again. So the steps stay correct when an Application is added.
- **Define the two terms once, in "Rules for every step".**: The child Applications of `cluster` are the Applications of the copy without `bootstrap` and `cluster`. One definition keeps each step short.
- **Keep the counts only in dated baselines.**: A dated count is a record of a measurement, so it stays true. Step 10 keeps the baseline of 2026-11-13 and adds the baseline of 2026-11-22. The finalizer count of the rule (2026-11-12) moves into the baseline of 2026-11-13 with its own date.

## Rejected alternatives

- **Change each count to 36**: the next new Application makes the counts false again.
- **A shell command in each step that counts the list**: the shared checks already count the live Applications, and a second command in each step makes the steps longer with no new check.
- **Delete the old baseline**: the issue asks to keep it, and it shows how the environment changed.
