"""GitHub token samples built in code, so no test source holds a literal token (#1398)."""

from __future__ import annotations

import base64
import json


def _base64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def installation_token() -> str:
    """A ``ghs_APPID_JWT`` installation token, the format GitHub rolled out in 2026.

    The 64-byte signature encodes to a ``-`` and ends in a letter (A, Q, g or w), as every
    64-byte value does, so a match that ends on a word boundary covers the whole token.
    """
    header = _base64url(json.dumps({"alg": "ES256", "typ": "JWT"}).encode())
    payload = _base64url(json.dumps({"iss": "example.com", "exp": 1791590400}).encode())
    signature = _base64url(bytes(range(64)))
    return f"ghs_15368_{header}.{payload}.{signature}"
