# Design

## Decisions
- Triggers: a push to `main` with `paths: ["docs/**", ".github/workflows/pages.yml"]`, and `workflow_dispatch`. The native `paths` filter starts no run for a push that changes no site file. A manual run rebuilds the site with no commit.
- Jobs: the form of the GitHub starter workflow for Jekyll (`pages/jekyll-gh-pages.yml` of `actions/starter-workflows`). The `build` job runs `actions/checkout`, `actions/configure-pages`, `actions/jekyll-build-pages` with `source: ./docs` and `upload-pages-artifact`. The `deploy` job runs `actions/deploy-pages` in the `github-pages` environment.
- Versions: `actions/jekyll-build-pages` v1.0.13, the version of the `Docs Site Build` check, so the pull request and the deployment build with the same image. The newest release of each other action, pinned by commit SHA: `configure-pages` v6.0.0 (2026-03-25), `upload-pages-artifact` v5.0.0 (2026-04-10) and `deploy-pages` v5.0.1 (2026-09-01). `actions/checkout` has the SHA that `ci.yml` uses.
- Permissions: `permissions: {}` for the workflow. The `build` job gets `contents: read` and `pages: read`, because `configure-pages` and the GitHub metadata plugin of the builder read the Pages site. Only the `deploy` job gets `pages: write` and `id-token: write`.
- Concurrency: the group `pages` with `cancel-in-progress: false`, as in the starter workflow. A newer run replaces a pending run, and no run stops a deployment in progress.
- Timeouts: each job has `timeout-minutes: 10`. `deploy-pages` stops its own wait after 300000 ms (5 minutes), before the job limit. The build steps have no limit of their own, so the job limit is their inner limit. In 40 runs of the legacy build, the longest build job took 32 s and the longest deploy job took 18 s.
- The pull request build of the site stays in the `docs-site` job of `ci.yml`. #4653 moves the path checks into filtered workflows of their own.

## Rejected alternatives
- Keep the legacy build. It starts 3 jobs on each push to `main`, also when the push changes no file under `docs/`. Owner decision O5 of the CI audit (2026-11-11) asks for a workflow with a `docs/**` filter.
- A deploy job in `ci.yml` with a change filter step. `ci.yml` runs on each push to `main`, so the job would start, skip its steps and use a runner slot. The native `paths` filter of a workflow of its own starts no job.
- The permissions of the starter workflow at the workflow level (`pages: write` and `id-token: write` for every job). The `build` job needs no write scope.
- A condition that skips the deployment while the Pages source is a branch. The README of `deploy-pages` v5.0.1 says that, with a branch source, a deployment from that branch is accepted. The `github-pages` environment allows deployments from `main` only, and the workflow deploys only from `main`. So the workflow works before and after the owner switch, and needs no condition.
- The link check (`lychee`) in the Pages workflow. The `Docs Site Build` check runs it on the pull request before the merge, and a second run on `main` finds the same result.
- The builder image by digest with `docker run`, as the `Docs Site Build` check does. That check runs the image with no network, which the action cannot do. For the deployment, the action is the supported interface, and it gives the builder the token that the metadata plugin uses.
