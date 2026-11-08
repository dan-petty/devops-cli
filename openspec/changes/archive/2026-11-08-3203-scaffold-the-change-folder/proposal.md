# Proposal: #3203

## Why
Every pull request starts with an OpenSpec change folder, and previous manual creation broke the project form in recurring ways. Closes #3203.

## What Changes
Add `devops openspec new <issue>` to create the change folder in project form with `.openspec.yaml`, `proposal.md`, `design.md`, `tasks.md`, and spec deltas for specified capabilities. Derives slug and branch name with `slug_from_title` shared with `devops repos worktrees add --title`. Gates unfilled scaffolds in `devops openspec check`. Adds project agent skills.

## Capabilities
- `openspec-scaffold`: scaffolding change folders in project form.
- `repos-worktrees-add`: deriving type and slug from issue title.

## Impact
Improves plan consistency across human and automated contributors. Prevents unmerged skeleton text from reaching review. Fits in one pull request.

## Feasibility
Confirmed against `openspec` 1.14.3 (`openspec new change`), `devops_cli.git.branch_form`, and `devops_cli.openspec.gate`.

## Existing Tool Considered
OpenSpec (Fission-AI/OpenSpec) creates a generic skeleton without project conventions, marker gate, or branch slug integration. A thin wrapper is used. Cost to build: 100k tokens and 5 hours. Internal code deleted: None.
