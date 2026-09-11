"""Text normalization, character mapping, and line deduplication utilities."""

from __future__ import annotations

import unicodedata

_UNICODE_REPLACEMENTS: dict[str, str] = {
    "\u202f": " ",  # narrow no-break space
    "\u00a0": " ",  # no-break space
    "\u200b": "",  # zero-width space
    "\u2009": " ",  # thin space
    "\u200a": " ",  # hair space
    "\u2002": " ",  # en space
    "\u2003": " ",  # em space
    "\u3000": " ",  # ideographic space
    "\ufeff": "",  # zero-width no-break space / BOM
    "\u2011": "-",  # non-breaking hyphen
    "\u2010": "-",  # hyphen
    "\u2012": "-",  # figure dash
    "\u2013": "-",  # en dash
    "\u2014": "-",  # em dash
    "\u2018": "'",  # left single quote
    "\u2019": "'",  # right single quote
    "\u201c": '"',  # left double quote
    "\u201d": '"',  # right double quote
    "\u201a": "'",  # single low-9 quote
    "\u201e": '"',  # double low-9 quote
    "\u2032": "'",  # prime
    "\u2033": '"',  # double prime
    "\u2026": "...",  # ellipsis
}

_TRANSLATE_TABLE = str.maketrans(_UNICODE_REPLACEMENTS)


def normalize_unicode_text(text: str) -> str:
    """Normalize non-standard Unicode spaces, hyphens, and quotes to standard ASCII."""
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKC", text)
    return normalized.translate(_TRANSLATE_TABLE)


def unique_lines(text: str) -> str:
    """Preserve only the first instance of each line or string in text or thinking responses using a set."""
    if not text:
        return ""
    seen: set[str] = set()
    result: list[str] = []
    for line in text.splitlines():
        trimmed = line.strip()
        if not trimmed:
            if result and result[-1] != "":
                result.append("")
            continue
        if trimmed not in seen:
            seen.add(trimmed)
            result.append(line)
    return "\n".join(result)
