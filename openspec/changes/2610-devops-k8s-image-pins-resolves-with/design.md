# Design

## Decisions

- **Use tag_digest from src/devops_cli/docker/registry.py instead of pinning crane in tools.lock**: tag_digest already sends a HEAD request, handles the 401 Bearer token challenge, is tested, and is used by devops argo cd apps status. Pinning crane adds a new binary, a new fake, and a new contract suite for the same read.
- **Remove image_reference from k8s/image_pins.py and use tagged_image from docker/registry.py**: One split stays in docker/registry.py. A second split in k8s/image_pins.py duplicates the reference grammar and drifts from it.
- **Double the registry at the HTTP edge with an httpx2 client in tests**: The resolver no longer calls a subprocess. A process-level fake is no longer needed. An HTTP-level double tests the actual wire protocol.
- **Keep a _normalize_reference helper in k8s/image_pins.py for Docker Hub shorthand**: tagged_image rejects references without a named registry host. Rendered manifests use Docker Hub shorthand (nginx:1.27). The normalization prepends docker.io/library/ before the split. This is a transformation, not a split.

## Rejected alternatives

- **Pin crane in tools.lock and call crane digest as a subprocess**: The design of #1997 (openspec/changes/archive/2026-10-29-1997-argo-image-pin-drift/design.md) rejected crane: it needs a new pin, a new fake, and a new contract suite. tag_digest already does the same HEAD read.
- **Keep ImagetoolsFake and add a new fake for tag_digest HTTP calls**: The resolver no longer calls a subprocess. A process-level fake is no longer needed. An HTTP-level double is simpler and tests the wire protocol directly.
- **Keep image_reference in k8s/image_pins.py alongside tagged_image**: Two splits of the same reference grammar will drift. The design of #1997 keeps one split in docker/registry.py.
