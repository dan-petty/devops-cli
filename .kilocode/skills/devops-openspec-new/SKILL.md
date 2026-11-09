---
name: devops-openspec-new
description: Scaffold the OpenSpec change folder of an issue in project form. Use when you start planning an issue.
---

# Scaffold an OpenSpec Change Folder

Do not write change files by hand. The `devops openspec new` command creates the change folder in project form.

## Steps

1. Run `uv run devops openspec new <issue>` (or with `--dry-run` to preview).
2. Follow the printed next steps to complete the proposal, design, tasks and specs.
3. Replace every line ending with the scaffold marker `<!-- devops-openspec-new: replace -->` before merging.
