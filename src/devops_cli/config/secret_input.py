"""Read one credential from a file or stdin, for `--from-file` of the commands that take one.

`devops config set --from-file` stores the credential in the OS keyring, and
`devops gh secret sync --from-file` seals it into GitHub, so both keep one rule for the input.
"""

from __future__ import annotations

from typing import BinaryIO

from devops_cli.config.constants import CONST_SECRET_FILE_MAX_BYTES
from devops_cli.lang import MESSAGES


def _read_to_end(source: BinaryIO, limit: int) -> bytes | None:
    """Every byte up to the end of `source`, or None once more than `limit` bytes arrive.

    The io contract lets one read of a terminal return less than it asks for before the end, so
    the loop reads until a read returns nothing.
    """
    data = bytearray()
    while chunk := source.read(limit + 1 - len(data)):
        data += chunk
        if len(data) > limit:
            return None
    return bytes(data)


def read_secret_input(source: BinaryIO) -> str:
    """The credential that `source` holds, as its UTF-8 text, with no line added or removed.

    An input that is larger than `CONST_SECRET_FILE_MAX_BYTES`, not UTF-8 or empty raises
    `ValueError`. No message quotes the input.
    """
    raw = _read_to_end(source, CONST_SECRET_FILE_MAX_BYTES)
    if raw is None:
        raise ValueError(
            MESSAGES.config.from_file_oversize.format(limit=CONST_SECRET_FILE_MAX_BYTES)
        )
    try:
        secret = raw.decode("utf-8")
    except UnicodeDecodeError:
        # The decode error quotes the bytes it could not decode, and they are part of the secret.
        raise ValueError(MESSAGES.config.from_file_not_text) from None
    if not secret.strip():
        raise ValueError(MESSAGES.config.from_file_empty)
    return secret
