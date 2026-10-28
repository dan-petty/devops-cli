# Design

## Decisions

### Two Bandit runs, one config

Bandit takes one severity threshold for a run, and `.bandit` cannot set a threshold for each target. The gate therefore runs Bandit over `src/` at low and over `tests/` at the threshold of `--severity` (medium by default), both with `--ini .bandit`. A target on the command line replaces the INI's `targets`, so the INI still lists `src,tests` for `devops scan report` and for a person who runs `bandit -r --ini .bandit`. A test holds the gate's two targets equal to the INI's targets.

### Skips in the shared config

B404, B603, B110 and B112 are low-severity rules. Skipping them in `.bandit` changes nothing for a run at medium, and it keeps the low run over `src/` to the findings that need a decision. Each skip has its reason in a comment in `.bandit`.

### A `# nosec` names its rule and a reason

A marker is `# nosec <rule>[,<rule>] # <reason>`. Bandit reads the rules up to the second `#`, and the reason after it is for a person. A test in `tests/test_architectural_invariants.py` refuses a marker in `src/` with no rule or no reason.

### The suppression ceiling rises

`src nosec` rises from 13 to 23. The 13 new markers mark findings that only look like a credential or a security use of `random`; before this change the gate did not show them at all. The gate gets stricter: a new low finding in `src/` fails it. The owner approves the new ceiling when they merge.

### `git` through the process seam

`run_subprocess` with `local_read=True` replaces each direct `subprocess.run` of `git`. The seam traces the run, isolates the environment and, when `git` is missing, returns exit code 127 with "Executable 'git' not found in PATH". Each caller keeps its fallback and logs the runner's error, which names the program.

## Rejected alternatives

- **Ruff's flake8-bandit rules for `src/`.** Ruff has per-file ignores, but `ruff check src --select S105` reports 69 strings where Bandit reports 6, for example every `*_TOKEN_ENV` name. It would need about 60 more markers.
- **One Bandit run at low over `src/` and `tests/`.** `tests/` has thousands of low findings (asserts and fixture passwords) by design.
- **A second Bandit run over `src/` at low beside the existing run.** It scans `src/` two times and adds about 30 s to the security row.
- **`shutil.which` in each `git` caller.** The process seam already reports a missing program, and the other `git` callers in `src/` use it.
- **`random.SystemRandom` for the jitter, to avoid a marker.** The jitter guards nothing; a marker with its reason states that, where a change of generator would only hide the finding.
- **Renaming `STATUS_PASS`, `ProbeStatus.PASS` and the secret names.** The names are correct; a rename to dodge a pattern would hide intent.
