"""Properties of secret redaction (`security/sanitizer.py`, #2545).

The line-by-line property of keyword masking stays in `tests/security/test_secret_redaction.py`,
beside the examples it generalizes.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from devops_cli.security.sanitizer import mask_secrets, mask_uri_credentials

_ALPHANUMERIC = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"

syntaxes = st.sampled_from(["data", "code"])
github_tokens = st.text(alphabet=_ALPHANUMERIC, min_size=36, max_size=36).map("ghp_{}".format)
prose = st.text(alphabet="abcdefghijklmnopqrstuvwxyz ,.:=/-_\n'\"", max_size=60)


@given(text=st.text(max_size=120), syntax=syntaxes)
def test_masking_masked_text_changes_nothing(text: str, syntax: str) -> None:
    """A second pass finds no secret in text that the first pass masked."""
    once = mask_secrets(text, syntax=syntax)

    assert mask_secrets(once, syntax=syntax) == once


@given(before=prose, token=github_tokens, after=prose, syntax=syntaxes)
def test_a_github_token_in_any_text_leaves_no_part_of_its_body(
    before: str, token: str, after: str, syntax: str
) -> None:
    """Neither the token nor its body without the prefix survives, whatever text surrounds it."""
    masked = mask_secrets(f"{before} {token} {after}", syntax=syntax)

    assert (token in masked, token.removeprefix("ghp_") in masked) == (False, False)


@given(
    scheme=st.sampled_from(["https", "http", "postgresql", "redis"]),
    user=st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789", min_size=1, max_size=12),
    password=st.text(alphabet=_ALPHANUMERIC + "-._~", min_size=1, max_size=24),
    host=st.sampled_from(["example.com", "db.example.com:5432", "192.0.2.10"]),
    rest=st.sampled_from(["", "/", "/x", "/db?sslmode=require"]),
)
def test_a_uri_keeps_everything_but_its_password(
    scheme: str, user: str, password: str, host: str, rest: str
) -> None:
    """Only the password of the userinfo becomes `***`; the scheme, user, host and path stay."""
    assert mask_uri_credentials(f"{scheme}://{user}:{password}@{host}{rest}") == (
        f"{scheme}://{user}:***@{host}{rest}"
    )
