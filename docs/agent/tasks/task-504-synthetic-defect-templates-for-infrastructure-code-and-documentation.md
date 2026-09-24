# Task 504: Synthetic Defect Templates for Infrastructure Code and Documentation

**Issue**: [#504](https://github.com/dan-petty/devops-cli/issues/504)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p2-medium`
**Scope**: `type/feature`, `scope/review`, `priority/p2-medium`

---

## 1. Description & Objectives

Infrastructure code and documentation get reviewed too, but the generator covers only a few YAML and Dockerfile patterns.

### Key Deliverables Completed:

- [x] **Terraform**:
  - `expose-public-access`:
    - sets `publicly_accessible`, `map_public_ip_on_launch` or `associate_public_ip_address` true;
    - turns S3 public access blocks off;
    - makes an ACL `public-read`;
    - or flips the default of a variable of those names.
  - `disable-encryption`: `encrypted`, `storage_encrypted`, `kms_encrypted`, key rotation and
    similar go false, or an encryption variable's default does.
  - `open-ingress`: an ingress rule's source range becomes `0.0.0.0/0`. That covers `ingress`
    blocks, `type = "ingress"` security group rules, network ACL rules with `egress = false`,
    and `aws_vpc_security_group_ingress_rule`. Egress, already open ranges and lists spread over
    lines are left alone.

  Blocks are matched by braces on code with strings and `#` comments blanked.
- [x] **Dockerfiles**:
  - `run-as-root`: `USER` becomes root.
  - `unverified-download`: drops `ADD --checksum`, or a `sha256sum -c` / `gpg --verify` segment
    of a continued `RUN`. The segment must sit mid-chain, so the chain still joins. A check
    inside an `if` is left alone.
  - The remote download itself is covered by `disable-tls-verify` and `pipe-to-shell`.
- [x] **Shell**:
  - `drop-strict-mode`: `set -e`, `set -eu`, `set -euo pipefail`, `set -o errexit`.
  - `unquote-expansion`: `"$var"` in a command. Assignments, `[[ ]]`, `case` words and comments
    are left alone.
  - `disable-tls-verify`: `curl --insecure` and `wget --no-check-certificate`, on https downloads
    only, since the flag changes nothing on plain http.
  - `pipe-to-shell`: `curl ... -o install.sh` becomes `curl ... | sh`, and `wget` becomes
    `wget -qO- ... | sh`.
  - `unverified-download`: a standalone checksum check. One whose result drives `||`, `&&` or a
    block is left alone.
  - `widen-file-mode`: `chmod 600` becomes `chmod 666`.

  The last four also apply to Dockerfiles.
- [x] **Kubernetes**:
  - `enable-host-network`: `hostNetwork: true` beside a pod's containers, unless the file
    already sets it.
  - `mount-host-path`: an `emptyDir: {}` volume becomes `hostPath: {path: /}`.
  - `drop-resource-limits`: a container's `resources.limits` goes. LimitRange `limits` are left
    alone.
- [x] **Technical documentation**:
  - `disable-tls-verify`, `pipe-to-shell` and `widen-file-mode` change example commands inside
    fenced code blocks and Hugo `highlight` / `codeFromInline` shortcodes, never prose.
  - `contradict-documented-default` changes a documented default (`true`/`false`,
    `enabled`/`disabled`, a number), so the page contradicts the code.
- [x] **Documentation**: the template table in `docs/SELF_IMPROVEMENT.md` lists every template
  and its languages.
- [x] **Automated Tests & Quality Gates**:
  - `tests/test_review_defects_infra.py`:
    - 26 injections with their exact mutated files and evidence;
    - 18 places that must be skipped: egress, open or multi-line ranges, unrelated variables,
      `USER root`, a checksum deciding an `if` or ending a `RUN`, a check driving `||`, plain
      http, `curl -k`, a continued line, assignments, `[[ ]]`, `case`, existing
      `hostNetwork`, LimitRange limits, `emptyDir` with options, prose, "no longer";
    - a corpus across Terraform, Dockerfile, shell, manifests and docs.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).

## 2. Verification on the Pinned Samples (#502)

Every site of the new and extended templates was applied to the infrastructure and documentation
samples, one at a time, and the mutated file checked:
- Terraform with python-hcl2;
- manifests with PyYAML (the Helm templates only as well as before, since they are not YAML
  until rendered);
- shell scripts with `bash -n`;
- each Dockerfile `RUN` with `bash -n`.

| Category | Sites |
| :--- | :--- |
| Terraform | `open-ingress` 9 (network ACL inbound rules), `expose-public-access` 1 (`map_public_ip_on_launch`) |
| Kubernetes/Helm | `enable-host-network` 5, `mount-host-path` 1, `drop-resource-limits` 1 |
| Dockerfiles and their scripts | `disable-tls-verify` 5, `unverified-download` 2, `drop-strict-mode` 10 |
| Shell | `unquote-expansion` 566 (nvm), `disable-tls-verify` 2, `drop-strict-mode` 1 |
| Documentation | `disable-tls-verify` 4 (Hugo code blocks), `contradict-documented-default` 2 |

None breaks its file. Two problems found along the way were fixed before the numbers above:
- nginx's `md5sum -c - ... || {` configuration check was taken for a standalone verification,
  and removing it broke the script;
- Hugo's code shortcodes were not seen as code blocks.

The samples have no `USER` lines, encryption settings or script downloads,
so `run-as-root`, `disable-encryption` and `pipe-to-shell` are exercised by the unit tests only.
A corpus over the samples injected 31 defects across 11 templates.
