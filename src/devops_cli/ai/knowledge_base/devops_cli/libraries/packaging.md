---
applies_to:
  - "pkg:pypi/packaging@26.*"
sources:
  - "https://packaging.pypa.io/"
  - "https://github.com/pypa/packaging"
reviewed: "2026-10-15"
tags:
  - "packaging"
  - "semver"
---

# Code Library: Packaging (SemVer & Python Specification Engine)

## 1. Project References

| Resource | Endpoint / URL |
| :--- | :--- |
| **Official Documentation** | [packaging.pypa.io](https://packaging.pypa.io/) |
| **Public Git Repository** | [github.com/pypa/packaging](https://github.com/pypa/packaging) |
| **Official PyPI Package** | [pypi.org/project/packaging](https://pypi.org/project/packaging/) (`26.3`) |
| **DevOps CLI Integration** | [`src/devops_cli/ai/kb.py`](../../../kb.py) |

---

## 2. General Information & Architecture

**Packaging** is the core library maintained by the Python Packaging Authority (PyPA) implementing fundamental Python packaging specifications (PEP 440 version identifiers, PEP 508 dependency specifiers, PEP 425 platform tags, and Semantic Versioning 2.0.0).

In `devops-cli`:
- **Knowledge Base Manual Matching**: `src/devops_cli/ai/kb.py` matches the `applies_to` entries of each manual (`pkg:pypi/packaging@26.*`, the Python pin) against the locked and installed versions with `SpecifierSet` and `Version`.
- **Defensive Parsing**: `kb.py` catches `InvalidSpecifier` and `InvalidVersion`, so an entry it cannot parse does not stop the match.
- devops-cli computes no release version: release-please derives it from the Conventional Commit titles on `main`.

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

### Version Range Matching
```python
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion


def version_in_range(version: str, specifier: str) -> bool:
    try:
        return SpecifierSet(specifier).contains(version)
    except InvalidSpecifier, InvalidVersion:
        return False


assert version_in_range("26.3", ">=26,<27")
```

---

## 6. Best Practices & Security Standards

1. **Catch `InvalidVersion` Defensively**: Always handle `packaging.version.InvalidVersion` gracefully when parsing user or tag inputs.
2. **Compare Versions, Never Strings**: Compare `Version` objects or use a `SpecifierSet`, never string or tuple splits.
