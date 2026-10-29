"""`devops k8s image-pins`: resolve each image that an Argo CD Application pins (#1994)."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from devops_cli.config.defaults import DEFAULT_CURRENT_PATH
from devops_cli.dry_run.state import set_dry_run
from devops_cli.exceptions.k8s import ImagePinError
from devops_cli.k8s.image_pins import (
    PinResolution,
    collect_image_pins,
    inspect_command,
    resolve_image_pins,
)
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import TableColumn, TablePayload, print, print_info, print_success


def _result_text(resolution: PinResolution) -> str:
    if resolution.planned:
        return "planned"
    return resolution.digest or f"not resolved: {resolution.error}"


def _failure_text(resolution: PinResolution) -> str:
    return MESSAGES.k8s.image_pins_failure.format(
        image=resolution.image,
        applications=", ".join(resolution.applications),
        registry=resolution.registry,
        error=resolution.error,
    )


def k8s_image_pins(
    root: Annotated[Path, typer.Argument(help=HELP.k8s.image_pins_root)] = DEFAULT_CURRENT_PATH,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
) -> None:
    """Render each Argo CD Application of the repository and resolve each image it pins in its
    registry, as an anonymous client, without pulling it. Exits 1, before it resolves an image, when
    an image has no digest and the latest tag or no tag, unless Image Updater moves it. Exits 1 when
    a registry does not hold an image or refuses the read. Docker Hub counts each read of a Docker
    Hub image as an anonymous pull, from the allowance of the network's public address, which the
    cluster's nodes may share; the CI job `image-pins` runs the check on a pull request that changes
    k8s/."""
    set_dry_run(dry_run)
    pins = collect_image_pins(root.resolve())
    if pins.latest:
        raise ImagePinError(
            MESSAGES.k8s.image_pins_latest.format(
                count=len(pins.latest),
                detail="; ".join(
                    MESSAGES.k8s.image_pins_latest_image.format(
                        image=image, applications=", ".join(applications)
                    )
                    for image, applications in pins.latest.items()
                ),
            )
        )
    resolutions = resolve_image_pins(pins)
    if resolutions:
        print(
            TablePayload(
                title=MESSAGES.k8s.table_title_image_pins,
                columns=[
                    TableColumn(header="Image"),
                    TableColumn(header="Applications"),
                    TableColumn(header="Registry"),
                    TableColumn(header="Result"),
                ],
                rows=[
                    [r.image, ", ".join(r.applications), r.registry, _result_text(r)]
                    for r in resolutions
                ],
            )
        )
    if pins.managed:
        print_info(MESSAGES.k8s.image_pins_managed.format(repositories=", ".join(pins.managed)))
    if pins.local:
        print_info(MESSAGES.k8s.image_pins_local.format(images=", ".join(pins.local)))
    if dry_run:
        print_info(
            MESSAGES.k8s.image_pins_dry_run.format(command=" ".join(inspect_command("<image>")))
        )
        return
    failures = [r for r in resolutions if not r.resolved]
    if failures:
        raise ImagePinError(
            MESSAGES.k8s.image_pins_failed.format(
                count=len(failures), detail="; ".join(_failure_text(r) for r in failures)
            )
        )
    print_success(MESSAGES.k8s.image_pins_resolved.format(count=len(resolutions)))
