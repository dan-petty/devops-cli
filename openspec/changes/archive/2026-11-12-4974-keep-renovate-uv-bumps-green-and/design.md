# Design

## Decisions
- Pin the digest in `.devcontainer/Dockerfile` now, and make the test strict. The service `Dockerfile` already names the uv image as `<version>@sha256:<digest>`, and `pinDigests` makes Renovate write the same form in the devcontainer. One form in both files lets one test line hold both pins, and Renovate opens no separate `pinDigest` pull request for the uv image.
- Set `updateNotScheduled: false` in the preset, not in the repository config, because every Service repository gets the same load problem.
- Keep the Monday schedule for the whole day (`* * * * 1`). The runs of Monday open the groups at 2 pull requests an hour, so a shorter window would leave groups for the next week.

## Rejected alternatives
- Accept a space or a digest after the uv version in the test: it keeps two forms of one pin, and Renovate still opens a `pinDigest` pull request.
- Remove the uv image from `pinDigests`: the rule of #4896 pins every Dockerfile image, and a tag without a digest can change under the same name.
- `commitHourlyLimit`: Renovate 44.235.1 reads the count of the hour once before a run writes its branches, so with one run every 2 hours it limits nothing.
- `prCommitsPerRunLimit` in this change: it is a global option of the self-hosted configuration, which #4905 adds.
