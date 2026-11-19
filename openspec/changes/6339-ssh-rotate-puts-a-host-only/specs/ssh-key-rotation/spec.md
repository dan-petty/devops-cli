## Purpose
SSH key rotation keeps each key to one purpose: only the project prefix registers on GitHub and signs commits, and every other prefix reaches hosts only.

## ADDED Requirements

### Requirement: A host-only prefix registers on no GitHub account
`devops ssh rotate` SHALL make no GitHub key request and SHALL run no `git config` command for a prefix that is not the project prefix.

#### Scenario: Rotate a host-only prefix
- **WHEN** a test runs `devops ssh rotate --prefix alpha --force` in a key directory that holds a key of that prefix, with `ssh.key_prefix` set to `devops-cli`
- **THEN** the GitHub fake receives no request, the temporary global git config of the test holds no `user.signingkey` and no `gpg.format`, and the new key file of the prefix exists in the key directory

### Requirement: The project prefix registers and signs
`devops ssh rotate` MUST register the new key on GitHub and set it as the git signing key when the prefix is the project prefix.

#### Scenario: Rotate the project prefix
- **WHEN** a test runs `devops ssh rotate --force` with `ssh.key_prefix` set to `devops-cli`
- **THEN** the GitHub fake receives the authentication key and the signing key of the new public key, and the temporary global git config of the test holds the new key as `user.signingkey`

### Requirement: A host-only rotation prints the host instruction
`devops ssh rotate` MUST print the new public key and one line that tells the person to put it on the hosts when the prefix is not the project prefix.

#### Scenario: Read the output of a host-only rotation
- **WHEN** a test runs `devops ssh rotate --prefix alpha --force`
- **THEN** the output holds the public key line of the new key and a line that tells the person to put the public key on the hosts, and holds no line about removing a key from GitHub

### Requirement: The rotate help names the prefix that registers
The help of `devops ssh rotate` MUST say that only the prefix in `ssh.key_prefix` registers on GitHub, and that every other prefix is for hosts only.

#### Scenario: Read the rotate help
- **WHEN** a test runs `devops ssh rotate --help`
- **THEN** the output names `ssh.key_prefix` as the only prefix that registers on GitHub and says that every other prefix is for hosts only
