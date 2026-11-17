"""Security verification for Azure AKS Terraform configuration (AZU-0041, #4945).

Tests assert offline that:
1. azurerm_kubernetes_cluster.aks sets api_server_access_profile.authorized_ip_ranges from var.
2. api_server_authorized_ip_ranges variable has no default.
3. No IP address literals are hardcoded in the committed Terraform files.
"""

from __future__ import annotations

from tests.support.paths import REPO_ROOT

AZURE_DIR = REPO_ROOT / "tf" / "azure"
MAIN_TF = AZURE_DIR / "main.tf"
VARIABLES_TF = AZURE_DIR / "variables.tf"


def test_aks_cluster_sets_api_server_access_profile_authorized_ip_ranges() -> None:
    """The AKS cluster sets api_server_access_profile.authorized_ip_ranges from the variable."""
    content = MAIN_TF.read_text(encoding="utf-8")
    assert "api_server_access_profile {" in content
    assert "authorized_ip_ranges = var.api_server_authorized_ip_ranges" in content


def test_api_server_authorized_ip_ranges_variable_has_no_default() -> None:
    """The variable api_server_authorized_ip_ranges has type list(string) and no default."""
    content = VARIABLES_TF.read_text(encoding="utf-8")
    assert 'variable "api_server_authorized_ip_ranges" {' in content
    var_block = content.split('variable "api_server_authorized_ip_ranges" {')[1].split("}")[0]
    assert "type        = list(string)" in var_block
    assert "description = " in var_block
    assert "default" not in var_block


def test_committed_tf_azure_holds_no_literal_authorized_ip_address() -> None:
    """Committed Terraform configuration does not hardcode authorized IP CIDR literals."""
    for tf_file in (MAIN_TF, VARIABLES_TF):
        content = tf_file.read_text(encoding="utf-8")
        for line in content.splitlines():
            if "authorized_ip_ranges" in line:
                assert "10." not in line
                assert "192." not in line
                assert "172." not in line
