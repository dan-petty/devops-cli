# file-analysis Specification

## Purpose
Detects programming languages and configuration formats from file paths, extensions, shebangs, and contextual markers.

## Requirements

### Requirement: C++ source file classification
The system SHALL classify files with extensions `.cc`, `.cpp`, `.cxx`, `.c++`, `.hh`, `.hpp`, and `.hxx` as `cpp`.

#### Scenario: Detecting C++ from file extensions
- **WHEN** language detection runs on a file ending in `.cc`, `.cpp`, `.cxx`, `.c++`, `.hh`, `.hpp`, or `.hxx`
- **THEN** the detected language is `cpp`

### Requirement: C and C++ header classification
The system SHALL classify `.h` header files containing C++ constructs as `cpp`, and other `.h` files as `c`.

#### Scenario: Header file with C++ constructs
- **WHEN** language detection inspects a `.h` file containing C++ templates, namespaces, or classes
- **THEN** the detected language is `cpp`

#### Scenario: Header file with C declarations
- **WHEN** language detection inspects a `.h` file containing standard C declarations
- **THEN** the detected language is `c`

### Requirement: Helm chart template classification
The system SHALL classify `.tpl` files residing inside a Helm chart alongside `Chart.yaml` as `helm`.

#### Scenario: Template file located in Helm chart
- **WHEN** language detection inspects a `.tpl` file situated beside or beneath `Chart.yaml`
- **THEN** the detected language is `helm`

#### Scenario: Standalone template file outside Helm chart
- **WHEN** language detection inspects a `.tpl` file without `Chart.yaml` in parent directories
- **THEN** the detected language is `plaintext`

### Requirement: Language detection without host MIME database
The system SHALL correctly identify file languages when the standard library MIME database contains no entries.

#### Scenario: Extension-based fallback succeeds without MIME mappings
- **WHEN** language detection evaluates C++, header, Dockerfile, YAML, or Helm template files with an empty MIME database
- **THEN** the detected language matches the expected language rule
