# Design

## Context

See `proposal.md` for the reason. `build_subprocess_env` and `find_repo_files` are public functions. A test can call each of them with crafted input and no double: the environment guard reads only the dictionary that the caller gives, and the target guard reads only the filesystem under `tmp_path`.

## Goals / Non-Goals

**Goals:**

- A test makes each guard refuse its input, and checks the error type, the message, the exit code and the error code, or the result.
- Each test fails when its guard is removed from `src/`.
- Delete the checks that no input reaches.

**Non-Goals:**

- Do not change the set of refused keys. The issue names six keys, and the guard refuses them.
- Do not change which files a review reads.

## Decisions

- **Call the public functions with crafted input.** The environment tests give `build_subprocess_env` a dictionary of overrides. The target tests make a repository, a tree beside it and symlinks under `tmp_path`.
  - *Rejected alternative:* Drive the guards through `run_subprocess` or `devops review path`. Evidence: the guards raise before a program starts, so a run of a program adds a process edge and its fake, and shows nothing more.
- **Write the refused keys as a literal in the test.** The test holds the guard to the six keys that the issue names.
  - *Rejected alternative:* Read the set from `src/`. Evidence: the set is a local name inside `build_subprocess_env`, and a test that reads the set from the code that it tests passes when a key goes from the set.
- **Run each environment case with isolation on and off.** The guard checks the overrides of the caller in both modes, and a change that moves the check into one mode fails the test.
- **Use the pattern `*/*.py` for the symlinked-directory case.** With this pattern, `rglob` follows the symlinked directory, so the candidate is no symlink and only the real-path check leaves it out. The test asserts that `rglob` gives the candidate first, so the test cannot pass with no candidate to leave out.
  - *Rejected alternative:* Use the default pattern `*`. Evidence: `rglob("*")` gives the symlinked directory itself and does not go into it, so the symlink check leaves it out and the real-path check is not reached.
- **Delete the `except OSError, RuntimeError` of the candidate filter.** A non-strict `resolve()` on Python 3.14 raises no `OSError` and no `RuntimeError`, as the proposal shows.
  - *Rejected alternative:* Keep the `except` and cover it with a patched `Path.resolve`. Evidence: docs/TESTING.md says that a line no public behavior reaches is deleted, not covered by a test that reaches past the public interface.

## Risks / Trade-offs

- [A later Python version makes a non-strict `resolve()` raise again] → The error then goes to the caller of `find_repo_files` and the review stops with that error. It does not quietly skip the file.
