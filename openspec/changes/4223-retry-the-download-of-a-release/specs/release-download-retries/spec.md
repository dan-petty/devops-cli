## Purpose
The download of a release archive by `devops install-tools`. A GitHub outage must not fail a check that a rerun would pass, and a failed download must not look like a checksum failure.

## ADDED Requirements

### Requirement: The installer retries a failed download
`devops install-tools` SHALL retry the download of a locked build when the server answers 429 or 5xx and when the connection fails. It SHALL wait between tries, for at least one minute in all. It SHALL NOT retry any other 4xx answer. When the tries end, the error SHALL name the URL and the HTTP status.

#### Scenario: Two 504 answers and then the archive
- **WHEN** the server answers 504 twice and then the archive of the lock
- **THEN** the installer installs and links the tool
- **AND** it waited between the three requests

#### Scenario: A lost connection and then the archive
- **WHEN** the first requests fail with a refused connection and a read timeout and the third answers the archive
- **THEN** the installer installs and links the tool

#### Scenario: A 504 answer that does not end
- **WHEN** the server answers 504 to every request
- **THEN** the install fails with an error that names the URL and the status 504
- **AND** no file of the tool stays

#### Scenario: A 404 answer
- **WHEN** the server answers 404
- **THEN** the install fails after one request with an error that names the URL and the status 404

### Requirement: A body that is not the archive is named before the checksum
The installer SHALL refuse a body of the format `gzip`, `tar.gz` or `zip` that lacks the magic bytes of that format, before it compares the SHA-256. The error SHALL be a `ToolDownloadError` that names the URL, says that the body is not an archive of that format, and gives the HTTP status. The installer SHALL keep the SHA-256 check for every body that passes.

#### Scenario: An HTML error page with status 200
- **WHEN** the lock names a `tar.gz` build and the server answers 200 with an HTML page
- **THEN** the install fails with a `ToolDownloadError` that names the URL and says that the body is not a tar.gz archive
- **AND** the error is not a checksum mismatch, and no file of the tool stays

#### Scenario: An archive with other bytes than the lock
- **WHEN** the server answers a real `tar.gz` archive whose SHA-256 is not the lock's
- **THEN** the install fails with a checksum mismatch
