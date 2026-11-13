"""The two documents that tell how a setting changes name the rule for the live ConfigMap (#4093).

The ConfigMap `devops-cli-config` lives in the cluster, and git does not hold it. A pull request
that removes, renames or tightens a setting that the example ConfigMap names must say how the live
ConfigMap changes first. `docs/CLUSTER.md` and `docs/ROADMAP_WORKFLOW.md` each hold that rule.
"""

from __future__ import annotations

import pytest

from tests.support.paths import REPO_ROOT

RULE = "removes, renames or tightens"


@pytest.mark.parametrize("document", ["docs/CLUSTER.md", "docs/ROADMAP_WORKFLOW.md"])
def test_the_document_holds_the_rule_for_the_live_configmap(document: str) -> None:
    """The phrase of the rule is in the document, on one line."""
    lines = (REPO_ROOT / document).read_text(encoding="utf-8").splitlines()

    assert sum(RULE in line for line in lines) == 1
