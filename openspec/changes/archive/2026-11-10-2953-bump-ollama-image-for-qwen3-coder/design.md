# Design

## Decisions

- **Pin the tag and the digest.** The digest fixes the exact image, as the other third-party pins under `k8s/` do. Renovate moves the tag and the digest together.
- **Widen the two tests.** `test_k8s_manifests.py` splits the image once at the first `:` and compares the tag before `@`. `test_renovate_config.py` accepts an optional `@sha256:<64 hex>` after the tag, so the manifests stay seen as pinned.
- **Add the spec `ollama-image-pin`.** It states the pin form so a test holds it.
- **The pull request closes the issue.** The project form requires `Closes #2953`. The bump does not fix the parser, so a new issue tracks the failure if it comes back.

## Rejected alternatives

- **Wait for a release with the parser fix.** The item said so, but the owner asked for the bump now.
- **Build a patched Ollama image.** The project would keep a fork of the parser, which costs more than the upstream release.
