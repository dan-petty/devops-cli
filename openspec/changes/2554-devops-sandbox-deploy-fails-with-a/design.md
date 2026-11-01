# Design

## Decisions

- **Pull in the sandbox deploy caller, not inside DockerEngineService.create_container.**: create_container is used by other callers that use locally-built images. Adding a network check there would add latency to every container creation. The sandbox deploy is the path that needs a registry image.
- **Check locally with images.get first, pull only when the image is absent.**: The image is local in the common case. A local check avoids a network round-trip on every deploy.
- **Raise DockerEngineError with the image reference and failure reason on pull failure.**: The raw 404 from the Docker API does not name the image. A clear error helps the user identify which image to pull manually.

## Rejected alternatives

- **Pull inside DockerEngineService.create_container.**: This would add a network check to every container creation, including callers that use locally-built images. The sandbox deploy is the only path that needs a registry image.
- **Replace containers.create with containers.run.**: containers.run starts the container immediately. This changes the create-then-start flow the sandbox deploy uses, where the runner controls start, wait, and teardown.
- **Always pull without checking locally first.**: A pull makes a network request even when the image is local. This adds latency to every deploy in the common case where the image is already present.
