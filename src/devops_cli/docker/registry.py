"""Read the digest that a tag names in its image registry, with the OCI distribution API (#1997).

A `HEAD` of the tag's manifest returns the digest in `Docker-Content-Digest`, so no manifest is
downloaded and nothing is pulled. A registry that asks for a Bearer token (GHCR, Docker Hub) gets
an anonymous pull token from the realm its challenge names, as `crane digest` and `docker pull`
do; the standard library parses the challenge. An image that needs credentials is a
`RegistryReadError`: devops-cli reads only public images here.

A reference names its registry host, or none, which is Docker Hub. docker-py splits it. Docker Hub
answers a manifest at `registry-1.docker.io`, not at `docker.io`, and a HEAD of a manifest there is
not counted against the anonymous pull allowance of the caller's address (#2610).
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.request import parse_http_list, parse_keqv_list

import httpx2

from devops_cli.exceptions.docker import RegistryReadError, RegistryTagNotFoundError

# The registry of a name that names none, as docker-py gives it, and the host that serves it.
_DOCKER_HUB = "docker.io"
_DOCKER_HUB_REGISTRY_HOST = "registry-1.docker.io"

# The manifest kinds a tag can name: a multi-platform index or list, or one image's manifest. The
# registry gives the digest of the kind it stores, which is what a pin names.
_MANIFEST_MEDIA_TYPES = ", ".join(
    (
        "application/vnd.oci.image.index.v1+json",
        "application/vnd.docker.distribution.manifest.list.v2+json",
        "application/vnd.oci.image.manifest.v1+json",
        "application/vnd.docker.distribution.manifest.v2+json",
    )
)


@dataclass(frozen=True)
class TaggedImage:
    """An image reference split into its parts; `tag` holds the digest of a reference that has one."""

    registry: str
    repository: str
    tag: str


def image_reference(image: str) -> tuple[str, str]:
    """The registry host and the repository of `image`, with no tag and no digest.

    docker-py splits it by the Docker reference grammar: the first component names a registry when
    it holds a `.` or a `:` or is `localhost`; any other name, and `index.docker.io`, is
    `docker.io`. docker-py strips only the digest of a reference that holds a tag and a digest, so
    the split is applied twice. docker-py is imported here, as a module-level import would slow
    every command that imports this module.
    """
    from docker.auth import resolve_repository_name
    from docker.errors import InvalidRepository
    from docker.utils import parse_repository_tag

    repository, _ = parse_repository_tag(parse_repository_tag(image)[0])
    try:
        return resolve_repository_name(repository)
    except InvalidRepository as exc:
        raise RegistryReadError(f"{image} is no valid reference: {exc}") from exc


def tagged_image(reference: str) -> TaggedImage:
    """Split `[<registry>/]<repository>[:<tag>][@<digest>]`; raise RegistryReadError for another form.

    A name that names no registry is on Docker Hub, as `docker.io`. A reference with a digest gives
    the digest as the tag, so the manifest of the digest is the one read, whatever tag it names too.
    """
    from docker.utils import parse_repository_tag

    registry, repository = image_reference(reference)
    _, tag = parse_repository_tag(reference)
    if not tag:
        raise RegistryReadError(f"{reference} names no tag, so it has no digest to look up.")
    return TaggedImage(registry=registry, repository=repository, tag=tag)


def _anonymous_token(client: httpx2.Client, challenge: str, reference: str, timeout: float) -> str:
    scheme, _, params = challenge.partition(" ")
    fields = parse_keqv_list(parse_http_list(params)) if scheme.lower() == "bearer" else {}
    realm = fields.pop("realm", "")
    if not realm:
        raise RegistryReadError(f"The registry of {reference} needs credentials to read it.")
    response = client.get(realm, params=fields, timeout=timeout)
    if response.status_code != httpx2.codes.OK:
        raise RegistryReadError(
            f"The registry of {reference} gives no anonymous pull token, so reading it needs "
            f"credentials (HTTP {response.status_code})."
        )
    body = response.json()
    token = (body.get("token") or body.get("access_token")) if isinstance(body, dict) else None
    if not isinstance(token, str) or not token:
        raise RegistryReadError(f"The token reply of the registry of {reference} holds no token.")
    return token


def tag_digest(reference: str, client: httpx2.Client, *, timeout: float) -> str:
    """Return the digest that the tag of `reference` names now, such as `sha256:...`.

    `reference` is `[<registry>/]<repository>:<tag>` or has a digest (see `tagged_image`); a name
    with no registry is on Docker Hub. Raises RegistryReadError when the registry
    gives no digest: the image needs credentials, or the reply has no `Docker-Content-Digest`.
    Raises RegistryTagNotFoundError, a RegistryReadError, when the registry answers HTTP 404: the
    tag is not there.
    """
    image = tagged_image(reference)
    registry, repository = image.registry, image.repository
    if registry == _DOCKER_HUB:
        # Docker Hub serves manifests at its registry host, and keeps an official image under
        # `library/`.
        registry = _DOCKER_HUB_REGISTRY_HOST
        repository = repository if "/" in repository else f"library/{repository}"
    url = f"https://{registry}/v2/{repository}/manifests/{image.tag}"
    headers = {"Accept": _MANIFEST_MEDIA_TYPES}
    response = client.head(url, headers=headers, timeout=timeout)
    if response.status_code == httpx2.codes.UNAUTHORIZED:
        token = _anonymous_token(
            client, response.headers.get("www-authenticate", ""), reference, timeout
        )
        headers["Authorization"] = f"Bearer {token}"
        response = client.head(url, headers=headers, timeout=timeout)
    if response.status_code != httpx2.codes.OK:
        error = (
            RegistryTagNotFoundError
            if response.status_code == httpx2.codes.NOT_FOUND
            else RegistryReadError
        )
        raise error(
            f"The registry gives no manifest for {reference} (HTTP {response.status_code})."
        )
    digest = response.headers.get("docker-content-digest", "")
    if not digest:
        raise RegistryReadError(f"The registry reply for {reference} names no digest.")
    return digest
