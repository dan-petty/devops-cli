"""The setting `roadmap.project_review.namespaces` (#6615): the project namespaces whose workloads
the project review can name. The load refuses an empty list, and a name that is not an RFC 1123
label, so a name cannot change the regular expression of a namespace matcher."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from devops_cli.config.settings import RoadmapProjectReviewConfig


def test_a_list_of_labels_loads_in_its_order() -> None:
    loaded = RoadmapProjectReviewConfig.model_validate({"namespaces": ["llm", "devops"]})

    assert loaded.namespaces == ["llm", "devops"]


@pytest.mark.parametrize(
    "namespaces",
    [
        pytest.param([], id="empty"),
        pytest.param(["devops|.*"], id="regular-expression"),
        pytest.param(["Devops"], id="capital-letter"),
        pytest.param(["-devops"], id="leading-hyphen"),
    ],
)
def test_an_empty_list_or_a_name_that_is_not_a_label_is_refused(namespaces: list[str]) -> None:
    with pytest.raises(ValidationError) as caught:
        RoadmapProjectReviewConfig.model_validate({"namespaces": namespaces})

    assert {error["loc"][0] for error in caught.value.errors()} == {"namespaces"}


def test_default_project_review_namespaces_includes_gpu_feature_discovery() -> None:
    """Default project review namespaces include `gpu-feature-discovery` (#6628)."""
    assert "gpu-feature-discovery" in RoadmapProjectReviewConfig().namespaces
