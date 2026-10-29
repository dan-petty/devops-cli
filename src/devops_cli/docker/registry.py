"""Read the digest that a tag names in its image registry, with the OCI distribution API (#1997).

A `HEAD` of the tag's manifest returns the digest in `Docker-Content-Digest`, so no manifest is
downloaded and nothing is pulled. A registry that asks for a Bearer token (GHCR, Docker Hub) gets
an anonymous pull token from the realm its challenge names, as `crane digest` and `docker pull`
do; the standard library parses the challenge. An image that needs credentials is a
`RegistryReadError`: devops-cli reads only public images here.

A reference names its registry host, as Argo CD Image Updater writes it. docker-py parses
references, but its package has no type hints, and its import would add a `type: ignore` over the
project's ceiling; #2603 types docker-py and moves the split to its parser.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.request import parse_http_list, parse_keqv_list

import httpx2

from devops_cli.exceptions.docker import RegistryReadError

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
    """An image reference `<registry>/<repository>:<tag>` split into its parts."""

    registry: str
    repository: str
    tag: str


def tagged_image(reference: str) -> TaggedImage:
    """Split `<registry>/<repository>:<tag>`; raise RegistryReadError for another form.

    The first path component is the registry when it holds a dot or a port, or is `localhost`,
    as the distribution reference grammar reads it. A tag holds no `/`, so the last `:` after the
    last `/` starts it.
    """
    registry, slash, path = reference.partition("/")
    if not slash or not ("." in registry or ":" in registry or registry == "localhost"):
        raise RegistryReadError(f"{reference} names no registry host, so its registry is unknown.")
    repository, colon, tag = path.rpartition(":")
    if not colon or not repository or not tag or "/" in tag:
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

    `reference` is `<registry>/<repository>:<tag>`. Raises RegistryReadError when the registry
    gives no digest: the image needs credentials, the tag is not there, or the reply has no
    `Docker-Content-Digest`.
    """
    image = tagged_image(reference)
    url = f"https://{image.registry}/v2/{image.repository}/manifests/{image.tag}"
    headers = {"Accept": _MANIFEST_MEDIA_TYPES}
    response = client.head(url, headers=headers, timeout=timeout)
    if response.status_code == httpx2.codes.UNAUTHORIZED:
        token = _anonymous_token(
            client, response.headers.get("www-authenticate", ""), reference, timeout
        )
        headers["Authorization"] = f"Bearer {token}"
        response = client.head(url, headers=headers, timeout=timeout)
    if response.status_code != httpx2.codes.OK:
        raise RegistryReadError(
            f"The registry gives no manifest for {reference} (HTTP {response.status_code})."
        )
    digest = response.headers.get("docker-content-digest", "")
    if not digest:
        raise RegistryReadError(f"The registry reply for {reference} names no digest.")
    return digest
