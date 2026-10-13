"""Property-based fuzzing tests for Argo GitOps drift event parsing.

Grounds property assertions in git-status(1) porcelain format specification
and GitOps manifest boundary invariants:
- Lines shorter than 4 characters are rejected.
- Path traversal attempts (`..`, `%2e%2e`) are strictly rejected.
- Only Kubernetes manifest extensions (.yaml, .yml, .json) produce drift events.
- Status code mapping respects deleted ('D'), created ('??', 'A'), and modified.
"""

from __future__ import annotations

from hypothesis import Phase, example, given, settings
from hypothesis import strategies as st

from devops_cli.argo.gitops import _parse_drift_event

_FUZZ_SETTINGS = settings(
    phases=[Phase.explicit, Phase.generate],
    derandomize=True,
    max_examples=35,
    deadline=None,
)

_TRAVERSAL_INJECTIONS = ("../", "..\\", "%2e%2e/", "/../", "\\..\\")
_MANIFEST_EXTS = (".yaml", ".yml")
_NON_MANIFEST_EXTS = (".json", ".py", ".txt", ".md", ".sh", ".go", ".rs", ".bin")


@_FUZZ_SETTINGS
@given(
    traversal=st.sampled_from(_TRAVERSAL_INJECTIONS),
    path_suffix=st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-", min_size=1, max_size=15),
    ext=st.sampled_from(_MANIFEST_EXTS),
)
@example(traversal="../", path_suffix="outside", ext=".yaml")
@example(traversal="%2e%2e/", path_suffix="secret", ext=".yml")
def test_gitops_drift_path_traversal_rejection_specification(
    traversal: str, path_suffix: str, ext: str
) -> None:
    """git-status(1) & path security: paths with traversal sequences must be rejected as None."""
    line = f" M {traversal}{path_suffix}{ext}"
    result = _parse_drift_event(line, now=1000.0)
    assert result is None


@_FUZZ_SETTINGS
@given(
    path_stem=st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-", min_size=1, max_size=20),
    ext=st.sampled_from(_NON_MANIFEST_EXTS),
)
@example(path_stem="script", ext=".py")
@example(path_stem="notes", ext=".txt")
@example(path_stem="configmap", ext=".json")
def test_gitops_drift_non_manifest_rejection_specification(path_stem: str, ext: str) -> None:
    """GitOps manifest boundary: non-manifest files (including .json) must not trigger GitOps drift events."""
    line = f" M k8s/{path_stem}{ext}"
    result = _parse_drift_event(line, now=1000.0)
    assert result is None


@_FUZZ_SETTINGS
@given(
    status_code=st.sampled_from([" M", "M ", " D", "D ", "??", " A", "A "]),
    path_stem=st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-", min_size=1, max_size=15),
    ext=st.sampled_from(_MANIFEST_EXTS),
)
@example(status_code=" M", path_stem="deployment", ext=".yaml")
@example(status_code=" D", path_stem="service", ext=".yml")
@example(status_code="??", path_stem="configmap", ext=".yaml")
def test_gitops_drift_manifest_status_mapping_specification(
    status_code: str, path_stem: str, ext: str
) -> None:
    """git-status(1) porcelain status mapping to GitOps change_type:

    'D' -> deleted, '??' or 'A' -> created, otherwise modified.
    """
    rel_path = f"k8s/{path_stem}{ext}"
    line = f"{status_code} {rel_path}"
    event = _parse_drift_event(line, now=12345.0)

    assert event is not None

    if "D" in status_code:
        expected_type = "deleted"
    elif "??" in status_code or "A" in status_code:
        expected_type = "created"
    else:
        expected_type = "modified"

    assert (event.change_type, event.timestamp) == (expected_type, 12345.0)
