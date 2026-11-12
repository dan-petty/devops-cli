# Design

## Decisions

- **The test bound is an option of the step.** The step gives `--timeout 60` to pytest. The global bound of `pyproject.toml` (600 s) stays for the other test runs. The contract test asserts the exact command and that the bound is more than 0 and shorter than the step limit in seconds.
- **The source keeps `hex`, and a test compares it with `components`.** The `hex` value lets a person read a color in the source and in a diff, and the Palette table of `docs/DESIGN.md` gives the same hex values. The test converts the `components` with coloraide and compares the result with `hex` in lowercase, so a check of a valid uppercase hex does not fail.

## Rejected alternatives

- **Remove `hex` from the sources.** DTCG 2025.10 makes `hex` optional, so this removes the duplicate. It was rejected because a person then reads and edits only floats such as `0.9647`, and the change rewrites 66 tokens in the three source files that other open items also change.
- **Set a lower global bound in `pyproject.toml`.** This changes the bound of every test run, which is not the problem of this item.
