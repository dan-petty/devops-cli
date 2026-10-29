"""A public OCI registry answered at the HTTP edge, as GHCR answers an anonymous client (#1997).

`stub_web.serve(RegistryFake(...))` installs it. A manifest request with no token gets 401 and a
Bearer challenge whose realm is the registry's `/token`; the token endpoint gives an anonymous pull
token, or 401 when the registry refuses anonymous pulls; the manifest request with the token gets
the tag's digest in `Docker-Content-Digest`, or 404 for a tag it does not hold.
"""

from __future__ import annotations

from urllib.parse import urlsplit

import httpx2

ANONYMOUS_TOKEN = "anonymous-pull-token"


class RegistryFake:
    """One registry host whose tags name the digests in `digests` (`<host>/<repo>:<tag>`)."""

    def __init__(
        self, digests: dict[str, str], *, host: str = "ghcr.io", anonymous: bool = True
    ) -> None:
        self.digests = digests
        self.host = host
        self.anonymous = anonymous

    def __call__(self, request: httpx2.Request) -> httpx2.Response | None:
        url = urlsplit(str(request.url))
        if url.netloc != self.host:
            return None
        if url.path == "/token":
            if not self.anonymous:
                return httpx2.Response(401, json={"errors": [{"code": "UNAUTHORIZED"}]})
            return httpx2.Response(200, json={"token": ANONYMOUS_TOKEN})
        name, _, tag = url.path.removeprefix("/v2/").partition("/manifests/")
        if request.headers.get("authorization") != f"Bearer {ANONYMOUS_TOKEN}":
            challenge = (
                f'Bearer realm="https://{self.host}/token",service="{self.host}",'
                f'scope="repository:{name}:pull"'
            )
            return httpx2.Response(401, headers={"www-authenticate": challenge})
        digest = self.digests.get(f"{self.host}/{name}:{tag}")
        if digest is None:
            return httpx2.Response(404)
        return httpx2.Response(
            200,
            headers={
                "docker-content-digest": digest,
                "content-type": "application/vnd.oci.image.index.v1+json",
            },
        )
