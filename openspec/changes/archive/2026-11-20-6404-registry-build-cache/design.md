# Design

## Decisions

- **Backend.** Each image build uses the BuildKit registry cache (`type=registry`). The devcontainer release uses it, and its export took 14.4 s, against 140.6, 61.3 and 140.2 s for the three `gha` exports of release run 44415593173.
- **Ref.** Each image keeps its cache in its own package, at `ghcr.io/${{ github.repository }}/<target>:buildcache`, in the same form as the devcontainer ref. A build with no target uses `service`.
- **Writer.** Only the `release.yml` build that pushes the image writes the cache, with `mode=max`. The release job already logs in to GHCR with `packages: write`. The pull request jobs only read (#4646), so they keep their permissions (`contents: read` and `security-events: write`).

- **No value check.** A check that reads the workflows and asserts the cache values goes (owner rule of 2026-11-16, owner decision of 2026-11-20). actionlint and zizmor check the form, and the build logs show the import and the export.

## Rejected alternatives

- **The GitHub Actions cache (`type=gha`).** The three exports took 140.6, 61.3 and 140.2 s, and the Actions cache of the repository holds 10.5 GB.
- **One tag for all images.** The export of one image replaces the cache index of the other images. #4928 found this with the default `gha` scope.
- **Every image build writes the cache.** A pull request job would need `packages: write`, and two jobs would replace the same tag at the same time (#4646).
- **`mode=min`.** It keeps only the layers of the final image, so the `deps` stages of a later build get no cache.
- **Read both the registry ref and the `gha` scope until the first release.** It keeps a warm cache for some pull requests for about one hour, and it needs a second change to remove the `gha` entries.
