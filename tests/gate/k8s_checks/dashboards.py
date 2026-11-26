"""The product dashboards folder `k8s/devops/dashboards` builds, and Grafana can keep each of
its dashboards (#7290).

The environment repository takes the folder as a remote base at a release tag, and no
kustomization of this repository reaches it, so a build of `k8s/devops` does not show that it
builds. Grafana keeps one dashboard for each uid. The checks read file names and uids, never a
panel value.
"""

from __future__ import annotations

from devops_cli.grafana import lint_dashboard_files
from tests.gate.k8s_render import applied_documents
from tests.support.paths import REPO_ROOT

DASHBOARDS_DIR = REPO_ROOT / "k8s" / "devops" / "dashboards"


def check_the_dashboards_folder_builds_one_config_map_of_every_dashboard_file() -> None:
    """The kustomization of the folder builds, and its ConfigMap holds each JSON file of the
    folder, so a renamed, missing or unlisted dashboard file fails here and not in the build of
    the environment repository."""
    (config_map,) = applied_documents(DASHBOARDS_DIR)
    files = sorted(path.name for path in DASHBOARDS_DIR.glob("*.json"))

    assert files != []
    assert sorted(config_map["data"]) == files


def check_no_two_product_dashboards_share_a_uid_or_fail_the_linter() -> None:
    """The dashboard linter accepts the files of the folder together, so no uid is in two of
    them: Grafana would keep only one of the two."""
    reports = lint_dashboard_files(sorted(DASHBOARDS_DIR.glob("*.json")))
    errors = [
        f"{report.source_file}: {issue.message}" for report in reports for issue in report.errors
    ]

    assert errors == []
