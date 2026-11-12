# Design

## Decisions

- **One pull request, one commit for each ecosystem.** The owner asked for one pull request with every known update (2026-11-12). The branch has a commit for actions and workflows, Dockerfiles and the devcontainer, the tools lock, OpenSpec, the cluster, and Python, so a reviewer can read each part alone. The squash merge makes one commit.
- **A major goes in only with evidence.** pre-commit-hooks 6, the loki 21, open-webui 18 and prometheus-operator-crds 33 charts, cachetools 8, diff-cover 11 and syrupy 7 go in: their changelogs name no change that the project uses, and the checks pass. The chart majors render the same objects with the values of the repository. Each other major has its own issue under #4893.
- **Coupled pins move together.** The argocd CLI 3.6.1 goes with the argo-cd chart 10.18.0 (server v3.6.1). The argo CLI 4.1.6 goes with the Argo Workflows image tag v4.1.6. cloudflared 2026.11.0 goes in the tools lock, the devcontainer image and the cluster. ruff 0.17.4 goes in `pyproject.toml` and the ruff-pre-commit hook.
- **A test reads a pin; it does not repeat it.** Where an update changed a literal in a test, the test now reads the version from the tools lock, the record, or checks the form of a digest (AGENTS.md rule 11): the tflint, Node tool and Dev Containers CLI tests, the registry digest test, and the archive date of the OpenSpec record. The next Renovate update of these pins changes no test.
- **Recordings are made again inside pytest only.** The OpenSpec runs were recorded with 1.17.0 by a scratch test marked `live("openspec")` that called `record_scenarios()`, so the isolation of the suite applied. The scanner recordings have no such route, so semgrep, osv-scanner, pluto and tflint stay at their pins (#5083).
- **google-genai is held below 3 in the repository config.** pydantic-ai 2.67 and later cap it below 3 and the lock keeps pydantic-ai 2.59, so lock maintenance would move google-genai alone. The hold is a fact of this repository's lock, so it goes in `.github/renovate.json`, not in the preset that every Service repository extends. The pydantic-ai issue removes it.

## Rejected alternatives

- **Let Renovate open the updates.** About 30 groups would open at once against an account cap of 20 concurrent CI jobs, which is the flood the owner wants to stop.
- **Take the migration majors with the pin only.** Each one fails a check or needs a backup, a data migration or a host check (see the issues).
- **Edit a recording by hand.** A recording stands for the real tool; a hand edit hides a change of its output.
