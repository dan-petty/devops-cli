# Design

## Decisions
- A `RUN` step holds each check whose result does not depend on the runtime sandbox, the entrypoint or the image metadata.
- The image under test is a build argument with a `:local` default. The pull request and the release use the same stage text, and the release tests the digest that it pushed, not a second build (#6407).
- The pull request builds the stages with `--builder default`, the Docker Engine of the runner, which holds the loaded images. The container builder cannot read them.
- The checkout bootstrap of the runner stays a `docker run`. It runs on a read-only root file system with all capabilities dropped, as the Job does, and a `RUN` step cannot.

## Rejected alternatives
- Stages inside `Dockerfile`: a stage that starts FROM `service` comes after `service`, so a build with no `--target` would build the test stage.
- Named contexts (`--build-context`): hadolint reads each `FROM <name>` as an image with no tag (DL3006).
- A bake file with `target:` contexts: it changes each build step, and the release must test the pushed digest.
- All checks as `RUN` steps: it would drop the checks of the entrypoint and of the sandbox.
- The test suite in a stage: it is #6408.
