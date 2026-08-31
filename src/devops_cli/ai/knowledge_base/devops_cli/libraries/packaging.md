# Code Library: Packaging (SemVer & Python Specification Engine)

## 1. Project References

| Resource | Endpoint / URL |
| :--- | :--- |
| **Official Documentation** | [packaging.pypa.io](https://packaging.pypa.io/) |
| **Public Git Repository** | [github.com/pypa/packaging](https://github.com/pypa/packaging) |
| **Official PyPI Package** | [pypi.org/project/packaging](https://pypi.org/project/packaging/) (`26.3`) |
| **DevOps CLI Integration** | [`src/devops_cli/commands/release.py`](file:///workspaces/devops-cli/src/devops_cli/commands/release.py) • [`src/devops_cli/commands/uv.py`](file:///workspaces/devops-cli/src/devops_cli/commands/uv.py) |

---

## 2. General Information & Architecture

**Packaging** is the core library maintained by the Python Packaging Authority (PyPA) implementing fundamental Python packaging specifications (PEP 440 version identifiers, PEP 508 dependency specifiers, PEP 425 platform tags, and Semantic Versioning 2.0.0).

In `devops-cli`:
- **Release Version Validation**: Parses and compares version strings during release preparation (`devops release prepare`).
- **Semantic Version Bumping**: Validates `major.minor.patch` progression and ensures tags match `v<version>` standards.
- **Dependency Specifier Audits**: Validates package constraints in `pyproject.toml`.

---

## 3. Comparable Projects & Tradeoffs

| Library | Strengths | Weaknesses | Why `devops-cli` Chose Packaging |
| :--- | :--- | :--- | :--- |
| **`packaging`** | Official PyPA standard, 100% PEP 440 / PEP 508 compliant, robust version comparison (`Version("1.0.0") < Version("1.1.0")`). | Strict syntax rules. | **Selected**: The canonical standard for all Python package version operations. |
| **`semver`** | Dedicated SemVer 2.0.0 library. | Strict SemVer only, lacks PEP 440 compatibility (cannot parse Python alpha/beta/dev releases like `.dev0`). | Rejected: Python toolchains require PEP 440 + SemVer support. |
| **String / Tuple Splits (`tuple(map(int, v.split('.')))`)** | Zero dependencies. | Extremely brittle, crashes on pre-releases (`1.0.0b1`), build metadata (`+cpu`), or non-numeric tags. | Rejected: Violates robust parser rules. |

---

## 4. Key Concepts & Core Patterns

1. **`Version`**: Represents a parsed version string supporting rich comparisons (`<`, `<=`, `==`, `!=`, `>=`, `>`):
   ```python
   from packaging.version import Version

   v = Version("0.2.5")
   assert v.major == 0 and v.minor == 2 and v.micro == 5
   ```
2. **`SpecifierSet`**: Evaluates whether a version satisfies a dependency range (`SpecifierSet(">=1.0,<2.0")`).

---

## 5. Common & Advanced Usage Examples

### Semantic Version Bump Calculation
```python
from packaging.version import Version, InvalidVersion


def calculate_version_bump(current_version_str: str, bump_type: str) -> str:
    try:
        v = Version(current_version_str)
    except InvalidVersion:
        raise ValueError(f"Invalid version string: '{current_version_str}'")

    if bump_type == "major":
        return f"{v.major + 1}.0.0"
    elif bump_type == "minor":
        return f"{v.major}.{v.minor + 1}.0"
    elif bump_type == "patch":
        return f"{v.major}.{v.minor}.{v.micro + 1}"
    else:
        raise ValueError(f"Unknown bump type: {bump_type}")
```

---

## 6. Best Practices & Security Standards

1. **Catch `InvalidVersion` Defensively**: Always handle `packaging.version.InvalidVersion` gracefully when parsing user or tag inputs.
2. **Enforce Semantic Strictness**: Require clean 3-part SemVer (`X.Y.Z`) for official production releases.
