# Tasks

The scratch files of this change are in `.data/agent/scratch/2373/` (outside git). `<scratch>` stands for that directory. Every command runs from the root of the worktree.

## 1. Fix the method and the idle-host guard

Reads: `pyproject.toml` (lines 228 to 253), `src/devops_cli/commands/ci.py` (lines 647 to 661). Changes: scratch files only.

- [ ] 1.1 Verify the tree to measure. The repeatable check is `git grep -n '^branch' -- pyproject.toml` (it must print nothing) and `uv run python -c "from devops_cli.commands.ci import _resolve_pytest_cmd as r; print(' '.join(r()))"` (it must print `uv run pytest --durations=10 --cov=src --cov-report=term-missing`). When the first command prints a line, #2163 has merged: stop, and comment on #2373 with the line, because the "lines" configuration cannot be run
- [ ] 1.2 Write `<scratch>/keep_cov.py` (a plugin that wraps `coverage.Coverage.combine` so that it calls the original with `keep=True`) and `<scratch>/run_config.sh <config> <round> <tsv> [pytest args]`. The script reads the 1-minute load from `/proc/loadavg`, runs `uv run pytest` with the options of the configuration under `TIMEFORMAT='%U %S %R'` and the bash `time` keyword, and appends one row of 8 tab-separated fields to `<tsv>`: config, round, user s, system s, wall s, load before the run, the last summary line of pytest, and the percent of the `TOTAL` line (`-` when there is none). The configs are `none` (`--durations=10`), `lines` (`--durations=10 --cov=src --cov-report=term-missing`), `branches` (`lines` plus `--cov-branch`), `ctrace` (`lines` with `COVERAGE_CORE=ctrace`), `lines-keep` (`lines` with `-p keep_cov` and `PYTHONPATH=<scratch>`) and `lines-noreport` (`--durations=10 --cov=src --cov-report=`)
- [ ] 1.3 Verify the script on one small test file. Run `<scratch>/run_config.sh none 0 <scratch>/smoke.tsv tests/commands/test_ci.py -q` and the same with `lines`, then `awk -F'\t' 'NF==8' <scratch>/smoke.tsv | wc -l` must print 2, and the `lines` row must end with a percent above 0. Run the smoke rows at any load: they are not results

## 2. Run the four configurations three times

Reads: `<scratch>/run_config.sh`. Changes: `<scratch>/runs.tsv`, `<scratch>/table.md`.

- [ ] 2.1 Before each run, wait for an idle host with `n=0; until awk '{exit !($1 < 2)}' /proc/loadavg; do n=$((n+1)); [ $n -gt 90 ] && exit 1; sleep 20; done` (at most 30 minutes). When the wait fails, stop the work and report the load that was read. Do not run on a loaded host, and do not change the limit of 2
- [ ] 2.2 Run three rounds. Each round runs `none`, `lines`, `branches` and `ctrace` in this order, with `<scratch>/run_config.sh <config> <round> <scratch>/runs.tsv` and no pytest argument, after the wait of task 2.1 for each run. A row is repeated (at most twice) when its `TOTAL` percent is `0%` for a coverage configuration, or when the passed and failed counts of its summary line differ from the rows of the first round
- [ ] 2.3 Verify the rows. These commands must print the numbers in brackets: `wc -l < <scratch>/runs.tsv` (12), `cut -f1 <scratch>/runs.tsv | sort | uniq -c` (3 for each of the four configurations), `awk -F'\t' '$6 >= 2' <scratch>/runs.tsv | wc -l` (0) and `cut -f7 <scratch>/runs.tsv | sed -E 's/ in .*//' | sort -u | wc -l` (1)
- [ ] 2.4 Write `<scratch>/table.md` with `uv run python`: the median of CPU time (user plus system) and of wall time of each configuration, from `statistics.median`, and the three runs of each. Verify with `grep -c '^| ' <scratch>/table.md` (it prints 6 at least: the header, the separator and the four rows)

## 3. Time the serial end of the coverage run

Reads: `<scratch>/run_config.sh`, `<scratch>/keep_cov.py`. Changes: `<scratch>/serial.tsv`.

- [ ] 3.1 After the wait of task 2.1, run `<scratch>/run_config.sh lines-keep 0 <scratch>/runs-keep.tsv` with no pytest argument. Verify that `ls .data/.coverage.* | wc -l` prints a number of 2 or more (the worker files stay) and that the row of `runs-keep.tsv` shows a `TOTAL` percent above 0
- [ ] 3.2 Time each command alone, three times each, with the bash `time` keyword and `TIMEFORMAT='%U %S %R'`: `uv run coverage combine --keep`, `uv run coverage report --show-missing` and `uv run coverage xml`. Append one row per run to `<scratch>/serial.tsv` (command, user s, system s, wall s). Verify with `wc -l < <scratch>/serial.tsv` (it prints 9) and `cut -f1 <scratch>/serial.tsv | sort | uniq -c` (3 for each command)
- [ ] 3.3 Write the median CPU time and wall time of each command in `<scratch>/table.md`, in a second table. Verify with `grep -c 'coverage combine\|coverage report\|coverage xml' <scratch>/table.md` (it prints 3 at least)

## 4. State the cost and report it

Reads: `<scratch>/table.md`. Changes: `<scratch>/report.md`, `<scratch>/pr-body.md`, a comment on #2163.

- [ ] 4.1 Write `<scratch>/report.md` from the medians, in plain sentences with numbers: the cost of the branch measurement as the median of `branches` minus the median of `lines`, in seconds of CPU time and of wall time and in percent; the cost of coverage as `lines` minus `none`; the cost of the `ctrace` core as `ctrace` minus `lines`; and the share of `coverage combine` plus `coverage report` in the median wall time of `lines`. Verify with `grep -c ' s' <scratch>/report.md` (it prints 4 at least) and `grep -n 'branch' <scratch>/report.md` (it prints a line with the cost in seconds)
- [ ] 4.2 When the share of task 4.1 is 5 % or more, wait for an idle host as in task 2.1 and run `<scratch>/run_config.sh lines-noreport <round> <scratch>/runs-noreport.tsv` for the rounds 1 to 3. Add the median saving in CPU and wall seconds against `lines` to `report.md`. When the share is under 5 %, write in `report.md` that no extra run was made and why. Verify with `grep -n 'share' <scratch>/report.md` (it prints the sentence) and, if the runs were made, `wc -l < <scratch>/runs-noreport.tsv` (it prints 3)
- [ ] 4.3 Post the statement on #2163 with `uv run devops gh api repos/dan-petty/devops-cli/issues/2163/comments -X POST -F body=@<scratch>/report.md` (the text names #2373 and leaves the decision on the thresholds to the owner). Verify with `uv run devops gh api repos/dan-petty/devops-cli/issues/2163/comments --jq '[.[] | select(.body | contains("#2373"))] | length'` (it prints 1)
- [ ] 4.4 Write `<scratch>/pr-body.md` for `uv run devops pr create --body-file`: what and why in short sentences, `Closes #2373`, the table of task 2.4 with the uptime reading of each run, the serial table of task 3.3 and the cost statement of `report.md`. Verify with `grep -c '^| ' <scratch>/pr-body.md` (it prints 10 at least) and `grep -c 'Closes #2373' <scratch>/pr-body.md` (it prints 1)
- [ ] 4.5 Verify that the change touches nothing else. `git diff origin/main --name-only | grep -v '^openspec/changes/'` must print nothing, `git diff origin/main -- pyproject.toml src .github` must print nothing (no threshold and no option changed), and `uv run devops ci test tests/commands/test_ci.py` must pass

## Workflow follow-up

- A change to the `--cov-report` option of the test row, if task 4.2 shows a saving, is a follow-up issue. File it with `devops roadmap intake` when the pull request opens. This change alters no option.
