# Proposal: #4810

## Why
The owner set a new rule on 2026-11-11: a security update or a bug fix must sometimes go in minutes after its release, and an update is correct when the surrounding tools support the version (#4810). The project text still held a minimum release age. `SECURITY.md` said "The two-week release rule still applies", and no document defined that rule. The SearXNG note in `.github/renovate.json` and step 1 of the SearXNG pin in `k8s/README.md` asked for a tag at least 14 days old. A released security fix could thus wait 14 days.

## What Changes
1. `CONTRIBUTING.md`, section 1, gets the bullet **Dependency Versions**: no minimum release age for a dependency, an image, a chart or a tool. Pin the newest release that fixes the known security and bug issues and that the surrounding tools support, and on which the tests pass. Take a release with a security fix or a bug fix on the day it is published. This is the one statement of the rule.
2. `SECURITY.md`, section "A Finding with No Fix", drops the two-week sentence and links to the rule.
3. The SearXNG rule of `.github/renovate.json` and the SearXNG pin steps of `k8s/README.md` drop the 14-day age. Step 1 chooses the newest tag that passes the tests of step 4, and takes a tag with a security fix or a bug fix on the day it is published.
4. `tests/core/test_renovate_config.py` checks that the SearXNG note names no tag age, and that the Renovate file sets no `minimumReleaseAge` and does not extend `config:best-practices`.

The Renovate configuration is a tracked file that two specs hold, so the change carries two spec deltas.

## Capabilities
- `searxng-service`: MODIFIED "A bump of the image tells the person what to check".
- `release-concurrency-and-renovate`: ADDED "Renovate sets no minimum release age".

## Impact
- Renovate behavior does not change: the file set no `minimumReleaseAge` before the change.
- A person merges a SearXNG bump without a wait for the tag age.
- No code under `src/` changes. The pull request fits one pull request.

## Feasibility
- `git grep` on `origin/main` found the minimum age in four places only: `SECURITY.md` line 61, `.github/renovate.json` lines 79 and 82, `k8s/README.md` step 1 of the SearXNG pin, and the `searxng-service` requirement with its test. No document defined the "two-week release rule".
- The Renovate preset page (https://docs.renovatebot.com/presets-config/, read 2026-11-11) lists the 16 presets of `config:recommended`, which this file extends. None of them sets `minimumReleaseAge`. `config:best-practices` extends `security:minimumReleaseAgeNpm`, which holds an npm update for 3 days.
- `uv run devops ci test tests/core/test_renovate_config.py` failed on the old SearXNG note (`assert (True, True, True) == (True, False, True)`) and passes after the change.
- The change edits two string values in `.github/renovate.json` (`description` and one `prBodyNotes` entry) and no key. `json.load` reads the file. The auto mode check refused `npx renovate-config-validator`, so the change did not run it.

## Existing Tool Considered
Renovate covers the need: with no `minimumReleaseAge`, it opens the pull request for a new release at once. The change edits text and one test file and builds no code. It deletes no internal code.
