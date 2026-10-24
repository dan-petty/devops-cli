"""The Valkey endpoint: one validated `valkey://` or `valkeys://` URL (#1113).

pydantic's `AnyUrl` with `UrlConstraints` refuses another scheme, a missing host, a bad port and an
IPv6 address with no brackets. The checks here refuse what `AnyUrl` accepts and what a Valkey URL
must not hold: a user name or a password, which belong in the OS keyring; a fragment; port 0; a
query key other than `db`; and a database that is not an integer of 0 or more. The database comes
from the path, as in `valkey://example.com:6379/2`, or from the query `?db=2`.

A refusal raises `ConfigurationError` with a message that names the setting. The message never
quotes the URL, because a refused URL can hold a password.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated
from urllib.parse import parse_qsl, unquote, urlsplit

from pydantic import AnyUrl, Field, TypeAdapter, UrlConstraints, ValidationError

from devops_cli.config.constants import (
    CONST_VALKEY_SCHEMES,
    CONST_VALKEY_TLS_SCHEME,
    CONST_VALKEY_URL_QUERY_KEYS,
)
from devops_cli.config.defaults import DEFAULT_VALKEY_PORT
from devops_cli.exceptions import ConfigurationError

_VALKEY_URL: TypeAdapter[AnyUrl] = TypeAdapter(
    Annotated[
        AnyUrl,
        UrlConstraints(
            allowed_schemes=sorted(CONST_VALKEY_SCHEMES),
            host_required=True,
            default_port=DEFAULT_VALKEY_PORT,
        ),
    ]
)
_DATABASE: TypeAdapter[int] = TypeAdapter(Annotated[int, Field(ge=0)])
_URL_SHAPE = "valkey://<host>:<port>/<db>"


@dataclass(frozen=True)
class ValkeyEndpoint:
    """The server a Valkey client dials: the scheme, the host, the port and the database.

    `host` is the name or the IP address as the resolver receives it: an IPv6 address has no
    brackets, and a name that is not ASCII is not percent-encoded.
    """

    scheme: str
    host: str
    port: int
    db: int

    @property
    def tls(self) -> bool:
        """Whether the connection uses TLS, with a certificate check against `host`."""
        return self.scheme == CONST_VALKEY_TLS_SCHEME


def parse_valkey_url(value: str, *, setting: str, written_by: str | None = None) -> ValkeyEndpoint:
    """The endpoint that the Valkey URL `value` names, or `ConfigurationError` naming `setting`.

    `written_by` names the commands that write a saved setting again, for the message of a refusal.
    """

    def refusal(reason: str) -> ConfigurationError:
        remedy = f" {written_by} writes it again." if written_by else ""
        return ConfigurationError(f"{setting} {reason}.{remedy}", key=setting)

    url = _valkey_url(value, refusal)
    if url.username or url.password:
        raise refusal("has a user name or a password. Keep the password in the OS keyring")
    if url.fragment is not None:
        raise refusal("has a fragment")
    if url.port == 0:
        raise refusal("has the port 0")
    # `AnyUrl` keeps the brackets of an IPv6 address and percent-encodes a name that is not ASCII.
    host = unquote(url.host or "").removeprefix("[").removesuffix("]")
    return ValkeyEndpoint(
        scheme=url.scheme,
        host=host,
        port=url.port or DEFAULT_VALKEY_PORT,
        db=_database(url, refusal),
    )


def _valkey_url(value: str, refusal: Callable[[str], ConfigurationError]) -> AnyUrl:
    """`value` as a URL with a Valkey scheme, a host and a valid port."""
    scheme = urlsplit(value).scheme
    if not scheme:
        raise refusal(f"has no scheme. Write it as {_URL_SHAPE}")
    try:
        return _VALKEY_URL.validate_python(value)
    except ValidationError as exc:
        error = exc.errors(include_url=False, include_input=False)[0]
        if error["type"] == "url_scheme":
            reason = f"has the scheme '{scheme}'. A Valkey URL starts with valkey:// or valkeys://"
        else:
            detail = error.get("ctx", {}).get("error", error["msg"])
            reason = (
                f"is not a valid URL: {detail}. "
                f"Write it as {_URL_SHAPE}, with an IPv6 address in brackets"
            )
        # The cause quotes the input, which can hold a password.
        raise refusal(reason) from None


def _database(url: AnyUrl, refusal: Callable[[str], ConfigurationError]) -> int:
    """The database that the path or the `db` query key of `url` names; 0 when neither does."""
    query = parse_qsl(url.query or "", keep_blank_values=True)
    unknown = sorted({key for key, _ in query} - CONST_VALKEY_URL_QUERY_KEYS)
    if unknown:
        raise refusal(f"has the query key '{unknown[0]}'. The only query key is db")
    path = (url.path or "/").removeprefix("/")
    databases = [*(text for key, text in query if key == "db"), *([path] if path else [])]
    if len(databases) > 1:
        raise refusal("names the database more than one time")
    try:
        return _DATABASE.validate_python(databases[0]) if databases else 0
    except ValidationError:
        raise refusal("names a database that is not an integer of 0 or more") from None
