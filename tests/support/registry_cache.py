"""A Semgrep registry ruleset in the user data root, as `devops review rules fetch` leaves it (#1144).

The ruleset is synthetic and has the shape of the registry's own, so no registry rule text is
committed.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from devops_cli.security.semgrep_registry import registry_cache_paths

CACHED_RULESET = (
    b"rules:\n"
    b"- id: example.lang.security.first.first\n"
    b"  pattern: first(...)\n"
    b"  message: first\n"
    b"  languages: [python]\n"
    b"  severity: ERROR\n"
)
CACHED_RULESET_DIGEST = f"sha256:{hashlib.sha256(CACHED_RULESET).hexdigest()}"
# A review writes the ruleset into its working directory under this name, which no file of the
# reviewed tree has, so Semgrep reads it as a local config and returns plain rule ids.
CACHED_RULESET_WORKDIR_NAME = f"{CACHED_RULESET_DIGEST.removeprefix('sha256:')}.yaml"
# A scan outside a review runs from the cache directory, and names the cached file by this name.
CACHED_RULESET_FILE_NAME = "p-default.yaml"
# Another ruleset, which a fetch could leave in the cache while a review runs.
REPLACED_RULESET = CACHED_RULESET.replace(b"first", b"second")


@pytest.fixture
def cached_default_ruleset() -> Path:
    """The file of the cached `p/default`, which holds `CACHED_RULESET`."""
    rules = registry_cache_paths("p/default").rules
    rules.parent.mkdir(parents=True)
    rules.write_bytes(CACHED_RULESET)
    return rules
