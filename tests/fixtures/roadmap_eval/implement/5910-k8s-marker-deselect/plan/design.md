# Design

## Decisions

- Use `item.get_closest_marker(marker) is not None` in `_deselect_by_marker` in `tests/conftest.py`. In pytest, `item.keywords` contains parent directory and package names as well as test identifiers and markers. `item.get_closest_marker()` resolves only actual pytest marks attached to the test item or its class/module/package.

## Rejected alternatives

- Leave `marker in item.keywords`: Rejected because every test inside a directory matching a marker name is inadvertently deselected.
- Rename the `tests/k8s/` directory: Rejected because the directory name correctly reflects the domain of the tests and matches project conventions.
