# Design

## Decisions

- **One file for each evaluation interval.** promtool reads `evaluation_interval` from the top level of a test file only. The hour-scale cases of `roadmap-service-activity` go to their own file at `1h`, as the hour-scale cases of `research`, `roadmap-service-tools` and `ai-spend` already are. The cases keep their names, series and expected alerts.
- **A group can have more than one file.** `ROADMAP_SERVICE_GROUP_TESTS` and `RULE_GROUP_TESTS` hold one pair of a group and a file for each file, so the group `roadmap-service-activity` has two pairs. `ROADMAP_SERVICE_GROUPS` keeps each group once, in table order. The promtool test runs once for each file, with the file stem as its test id, and checks that the file names only alerts of its group. A test that reads the files only, with no promtool, checks that the files of each group together test every alert of the group. Thus the check that each alert has a case stays, and it now runs also where promtool is not installed.
- **A guard on rounds, not on time.** The guard computes the rounds of each test group of each file: the last `eval_time` of its cases over the `evaluation_interval` of the file. It fails above 1,000 rounds. The other files make 390 or less, and the old activity file made 12,000. A bound on rounds holds on any host; a bound on elapsed time does not, and the project bans elapsed-time bounds in tests. The guard reads durations with `parse_duration` of `src/devops_cli/prometheus/client.py`.

## Rejected alternatives

- **Set `evaluation_interval: 1h` for the whole old file.** The minute-scale cases test waits and ranges of minutes, so an hourly step would change what they test.
- **Shorten the hour-scale cases.** The rule reads ranges of 3 and 7 days, so the cases need 150 to 200 hours of series.
- **Run the case only in CI, or mark it slow and skip it locally.** The case is a real check of an alert, and a skipped check is a lower quality bar.
- **A bound on the time of the promtool test.** It fails on a loaded host and passes a slow case on a fast host, and the project bans elapsed-time bounds in tests.
