# Design

## Where the release lives

Two files pin cloudflared. `k8s/cloudflared/deployment.yaml` names the image tag. `src/devops_cli/tools_lock/tools.lock` names the version, the URL and the SHA-256 of each platform build. Both move to 2026.10.4 in this change.

## Why the tests check a floor and the URLs

The floor is 2026.10.2, the first release built with Go 1.27.3. A later bump only has to stay at or above it, so the tests do not force every future bump to edit them.

In `tools.lock`, `version` names the install directory and each `sha256` checks only the bytes of its own `url`. A bump of `version` that leaves a `url` at the old release would install the old build under the new version, and the checksum would pass. The second test closes that gap.

## Rejected alternatives

- **Pin 2026.10.3, the image that the notice names.** Rejected: 2026.10.4 is the newest release, it holds the 2026.10.2 and 2026.10.3 changes, and the only runtime change after 2026.10.3 limits the debug endpoints of the metrics server. The diff 2026.10.3...2026.10.4 leaves `/metrics` and `/ready` in place.
- **Restart the pods and keep the old tag.** Rejected: the notice says that a restart of a container that uses the old image does not apply the fix. The tag must change.
- **Pin the image by digest.** Rejected: this repository pins the image of every manifest by tag, and a change of that convention is not part of this issue.
- **Set `noTLSVerify` for an origin that the new build rejects.** Not needed: the tunnel has no HTTPS origin, and the notice forbids it.
- **Add a Renovate rule in this change.** Rejected: the rule changes how many pull requests the repository gets and needs a decision of its own. The follow-up issue holds it.

## Test

Both tests are invariant tests of committed files, and they read no network. They fail on the pins of 2026.9.3 and pass on those of 2026.10.4.
