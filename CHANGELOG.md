# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

[Full Changelog](https://github.com/destination-earth-digital-twins/Deode-Prototype/compare/...HEAD)


## [Unreleased](https://github.com/destination-earth-digital-twins/Deode-Prototype/tree/HEAD)

### Added
- Add commit hash to an automatic tag derived from a branch. [\#24](https://github.com/destination-earth-digital-twins/Tactus-test-runner/pull/24) (@uandrae)
- added option to download gl binaries for testing with IAL PRs.
- removed bindir modification from ial_pr config files, so that the download path is used by default

### Fixed
- Correct erroneous config reference causing wrong binaries to be used in case of IAL pr testing[\#23](https://github.com/destination-earth-digital-twins/Tactus-test-runner/pull/30) (@uandrae)
- Fixed issue with gnu modifications in ial_pr runs  [\#23](https://github.com/destination-earth-digital-twins/Tactus-test-runner/pull/23) (@pardallio)
- Fixed Lumi IAL- pr configuration file [\#25](https://github.com/destination-earth-digital-twins/Tactus-test-runner/pull/25) (@pardallio)
- Fixed atos IAL- pr-large configuration file [\#29](https://github.com/destination-earth-digital-twins/Tactus-test-runner/pull/29) (@pardallio)
  
## [0.3.0] - 2026-02-16

Version used for testing of Deode-Workflow v0.25.0 using `reference_date=2026-02-14`

## [0.2.0] - 2025-12-16

Version used for testing of Deode-Workflow v0.24.0 using `reference_date=2025-12-15`

## [0.1.0] - 2025-12-11

### Added
v0.1.0 of `Tactus-test-runner` runs a number of tests for tactus
