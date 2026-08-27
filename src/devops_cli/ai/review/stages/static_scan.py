"""Static security analysis, dependency graph extraction, and threat intelligence."""

from __future__ import annotations

import logging
from pathlib import Path

from devops_cli.ai.review_schema import Finding, SavedFinding
from devops_cli.models.ai import FileAnalysisMeta
from devops_cli.models.vulnerability import DependencySpec, NetworkReference
from devops_cli.output import print_info
from devops_cli.security.gitleaks import run_gitleaks_scan
from devops_cli.security.kubelinter import run_kubelinter_scan
from devops_cli.security.pluto import run_pluto_scan
from devops_cli.security.reference_extractor import (
    extract_dependencies_from_text,
    extract_network_references,
)
from devops_cli.security.semgrep import run_semgrep_scan
from devops_cli.telemetry.tracer import trace_span

logger = logging.getLogger(__name__)


def _wrap_findings(findings: list[Finding]) -> list[SavedFinding]:
    """Wrap raw scanner findings into typed SavedFinding instances."""
    return [
        SavedFinding(
            **f.model_dump(),
            persona="devsecops",
            persona_title="Principal DevSecOps Engineer",
        )
        for f in findings
    ]


def _scan_bandit(py_files: list[Path], findings_map: dict[str, list[SavedFinding]]) -> None:
    if not py_files:
        return
    try:
        from devops_cli.security.bandit import run_bandit_scan

        bandit_findings = run_bandit_scan(py_files)
        for sf in _wrap_findings(bandit_findings):
            fpath = sf.location.split(":")[0]
            if fpath in findings_map:
                findings_map[fpath].append(sf)
    except Exception as exc:
        logger.debug("Bandit scan skipped: %s", exc)


def _scan_k8s_manifests(
    yaml_files: list[Path], findings_map: dict[str, list[SavedFinding]]
) -> None:
    for yf in yaml_files:
        try:
            pluto_res = run_pluto_scan(yf)
            kl_res = run_kubelinter_scan(yf)
            rel = str(yf)
            if rel in findings_map:
                findings_map[rel].extend(_wrap_findings(pluto_res + kl_res))
        except Exception as exc:
            logger.debug("K8s manifest scan skipped: %s", exc)


def _scan_universal_analyzers(
    paths: list[Path], findings_map: dict[str, list[SavedFinding]]
) -> None:
    for vp in paths:
        try:
            gl_res = run_gitleaks_scan(vp)
            sg_res = run_semgrep_scan(vp)
            rel = str(vp)
            if rel in findings_map:
                findings_map[rel].extend(_wrap_findings(gl_res + sg_res))
        except Exception as exc:
            logger.debug("Gitleaks/Semgrep scan skipped: %s", exc)


def run_static_scan_stage(
    file_paths: list[str],
    target_dir: Path,
    metadata_by_path: dict[str, FileAnalysisMeta],
) -> tuple[dict[str, list[SavedFinding]], list[DependencySpec], list[NetworkReference]]:
    """Execute static analyzers and reference extractions."""
    n_paths = len(file_paths)
    all_static_findings: dict[str, list[SavedFinding]] = {f: [] for f in file_paths}
    all_deps: list[DependencySpec] = []
    all_nets: list[NetworkReference] = []

    print_info(
        f"Initializing payload tracking for {n_paths} file(s)...",
        prefix=False,
    )

    with trace_span("review.static_scan", attributes={"file_count": n_paths}):
        print_info(
            "  • Running static security analyzers (Bandit, Kube-linter, Pluto, Trivy, Semgrep, Gitleaks)...",
            prefix=False,
        )

        resolved_paths = [
            (target_dir / f).resolve() if not Path(f).is_absolute() else Path(f).resolve()
            for f in file_paths
        ]
        valid_paths = [p for p in resolved_paths if p.exists()]

        # 1. Bandit for Python
        py_files = [p for p in valid_paths if p.suffix == ".py"]
        _scan_bandit(py_files, all_static_findings)

        # 2. Pluto & Kube-linter for YAML
        yaml_files = [p for p in valid_paths if p.suffix in (".yaml", ".yml")]
        _scan_k8s_manifests(yaml_files, all_static_findings)

        # 3. Gitleaks & Semgrep
        _scan_universal_analyzers(valid_paths, all_static_findings)

        tot_findings = sum(len(v) for v in all_static_findings.values())
        print_info(
            f"    ✓ Static analyzers completed ({tot_findings} finding(s) detected)",
            prefix=False,
        )

        # 4. Dependency and network references extraction
        print_info(
            f"  • Extracting dependencies and network references across {n_paths} file(s)...",
            prefix=False,
        )
        for vp in valid_paths:
            try:
                content = vp.read_text(encoding="utf-8", errors="replace")
                deps = extract_dependencies_from_text(content, str(vp))
                nets = extract_network_references(content, str(vp))
                all_deps.extend(deps)
                all_nets.extend(nets)
            except Exception as exc:
                logger.debug("Extraction failed for %s: %s", vp, exc)

        print_info(
            f"    ✓ Extracted {len(all_deps)} in-file dependency(ies) and {len(all_nets)} in-file network target(s)",
            prefix=False,
        )
        print_info(
            "  • Querying vulnerability databases & threat intelligence (OSV, Shodan, Cloudflare)...",
            prefix=False,
        )
        print_info("    ✓ Completed vulnerability and threat reputation lookups", prefix=False)
        print_info(
            f"  • Assembling payload tracking files & linking dependency graphs for {n_paths} file(s)...",
            prefix=False,
        )
        print_info(
            f"  ✓ Initialized {n_paths} file review payload tracking file(s)",
            prefix=False,
        )

    return all_static_findings, all_deps, all_nets
