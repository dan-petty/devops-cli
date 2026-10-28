# Proposal

## Why

Issue #2454: the owner made the roadmap Service's GitHub App on 2026-10-28 as `devops-cli-service`, with read and write on every repository permission, for planned repository-management work. ADR 0015, `k8s/README.md`, `k8s/devops/configmap.example.yaml` and two knowledge-base entries still name it `devops-roadmap`, the name #1647 planned, and list only the permissions the roadmap jobs need. The "Roadmap service" note in `k8s/README.md` also says that the Service waits on a separate item that moves the roadmap state to labels; #2399 (PR #2435) merged that item.

## What Changes

- The documents name the App `devops-cli-service`, and its bot login `devops-cli-service[bot]`.
- ADR 0015 gets an amendment line. It lists the permissions the roadmap jobs need and the broader grant the owner made, and its consequences record the risk of that grant: the key can change repository settings, Actions secrets and variables, environments and workflows, which AGENTS.md leaves to a person.
- The "Roadmap service" note says what the Service waits on now: the one-time move of the board's values to labels, and the App's setup (steps 1 to 3).
- No code or observable behavior changes, so the change has no spec delta (`skip_specs: true`). The code reads the App's name from `service.github_app.slug`. The tests keep `devops-roadmap` as an example slug.
- This change fits one pull request.

## Feasibility

- The owner gave the App's settings page (github.com/settings/apps/devops-cli-service), its App ID, and the grant of read and write on every repository permission, in the session of 2026-10-28.
- `git grep -n "devops-roadmap" -- docs k8s src` at main 4226904e lists each place, apart from the record and refine markers and a documentation anchor.
- `GitHubAppConfig` (`src/devops_cli/config/settings.py`) reads `slug` from the settings, and no source file names the App.

## Existing Tool Considered

A documentation change only; nothing is built, and nothing is deleted.
