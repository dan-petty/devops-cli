"""Invariant test proving declared dependencies for benchmark ranking."""

import tomllib

from tests.support.paths import REPO_ROOT


def test_declared_dependencies_numpy_and_pytrec_eval() -> None:
    root = REPO_ROOT
    pyproject_path = root / "pyproject.toml"
    uv_lock_path = root / "uv.lock"
    stub_path = root / "typings" / "pytrec_eval.pyi"

    with open(pyproject_path, "rb") as f:
        pyproject = tomllib.load(f)

    # 1. Assert numpy and pytrec-eval-terrier are in project dependencies
    deps = pyproject.get("project", {}).get("dependencies", [])
    dep_names = [dep.split("==")[0].split(">=")[0].strip() for dep in deps]
    assert "numpy" in dep_names, "numpy not declared in project dependencies"
    assert "pytrec-eval-terrier" in dep_names, (
        "pytrec-eval-terrier not declared in project dependencies"
    )

    # 2. Assert uv.lock package entries have resolved version and linux x86_64 wheel
    with open(uv_lock_path, "rb") as f:
        uv_lock = tomllib.load(f)

    packages = uv_lock.get("package", [])
    for pkg_name in ("numpy", "pytrec-eval-terrier"):
        matching = [p for p in packages if p.get("name") == pkg_name]
        assert matching, f"package {pkg_name} not found in uv.lock"
        pkg = matching[0]
        assert pkg.get("version"), f"package {pkg_name} has no resolved version in uv.lock"
        wheels = [w.get("url", "") for w in pkg.get("wheels", [])]
        has_linux_x86_64 = any(
            w.endswith(".whl") and "linux" in w and "x86_64" in w for w in wheels
        )
        assert has_linux_x86_64, f"package {pkg_name} has no linux x86_64 wheel in uv.lock"

    # 3. Assert typings/pytrec_eval.pyi has RelevanceEvaluator and evaluate
    assert stub_path.exists(), f"stub file {stub_path} does not exist"
    stub_content = stub_path.read_text(encoding="utf-8")
    assert "RelevanceEvaluator" in stub_content
    assert "evaluate" in stub_content

    # 4. Assert tool.mypy.overrides holds exactly one entry, with no pytrec_eval module
    mypy_overrides = pyproject.get("tool", {}).get("mypy", {}).get("overrides", [])
    assert len(mypy_overrides) == 1, (
        f"expected exactly 1 mypy override, found {len(mypy_overrides)}"
    )
    for override in mypy_overrides:
        assert "pytrec_eval" not in override.get("module", "")
