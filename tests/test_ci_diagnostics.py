"""Tests for the quality gate's slow-mount and slowest-test diagnostics."""

from __future__ import annotations

from pathlib import Path

from devops_cli.ci.diagnostics import slow_mount_fstype, slowest_tests

_MOUNTS = (
    "none / overlay rw,relatime 0 0\n"
    "C:\\134 /workspaces/devops-cli 9p rw,noatime,aname=drvfs 0 0\n"
    "/dev/sde /workspaces/devops-cli/.data ext4 rw,relatime 0 0\n"
    "/dev/sdf /srv ext4 rw,relatime 0 0\n"
    "D:\\134 /mnt/host\\040share 9p rw 0 0\n"
)


def test_a_workspace_on_a_9p_host_share_is_slow() -> None:
    """Verify a path under a 9p host share reports the share's filesystem type."""
    assert slow_mount_fstype(Path("/workspaces/devops-cli/src"), _MOUNTS) == "9p"


def test_the_most_specific_mount_decides() -> None:
    """Verify a Linux volume mounted inside a host share is not reported as slow."""
    assert slow_mount_fstype(Path("/workspaces/devops-cli/.data/cache"), _MOUNTS) is None


def test_a_linux_filesystem_is_not_slow() -> None:
    """Verify paths on ext4 and on the overlay root are not reported."""
    assert (
        slow_mount_fstype(Path("/srv/work"), _MOUNTS),
        slow_mount_fstype(Path("/opt/tools"), _MOUNTS),
    ) == (None, None)


def test_escaped_mount_points_are_decoded() -> None:
    """Verify the octal escapes /proc/mounts uses for spaces are decoded before matching."""
    assert slow_mount_fstype(Path("/mnt/host share/repo"), _MOUNTS) == "9p"


def test_slowest_tests_reads_the_durations_report() -> None:
    """Verify the lines of pytest's durations report are returned, and nothing after it."""
    output = (
        "....\n"
        "==================== slowest 10 durations ====================\n"
        "120.22s call     tests/test_secops.py::test_trivy_dry_run\n"
        "60.13s call     tests/test_secops.py::test_kubelinter_dry_run\n"
        "\n"
        "==================== 6250 passed in 514.78s ====================\n"
    )

    assert slowest_tests(output) == [
        "120.22s call     tests/test_secops.py::test_trivy_dry_run",
        "60.13s call     tests/test_secops.py::test_kubelinter_dry_run",
    ]


def test_slowest_tests_without_a_report_is_empty() -> None:
    """Verify output without a durations report yields no lines."""
    assert slowest_tests("5 passed in 1.00s\n") == []
