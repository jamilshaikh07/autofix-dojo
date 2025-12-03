# Changelog

All notable changes to autofix-dojo will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2024-12-03

### Initial MVP Release

First public release of autofix-dojo - an autonomous vulnerability fixer for DefectDojo and Kubernetes.

### Added

- **DefectDojo Integration**
  - REST API client for fetching vulnerability findings
  - Pagination support for large finding sets
  - Filtering by severity level (Critical, High, Medium, Low)
  - Product-scoped queries via `DEFECTDOJO_PRODUCT_ID`

- **Image Version Analysis**
  - Semantic version parsing (major.minor.patch)
  - Known-safe version mappings for common images (nginx, python, node, redis, postgres)
  - Automatic patch-level bump suggestions
  - Confidence scoring (high/medium) for suggestions

- **Git Automation**
  - Branch creation with timestamp and unique ID
  - Kubernetes manifest updates (Deployments, StatefulSets)
  - Helm values.yaml tag updates
  - Automated commits with descriptive messages
  - Pull request creation via GitHub CLI (`gh`)
  - GitLab merge request support via `glab`

- **SLO Tracking**
  - JSON-based metrics storage
  - Per-run tracking (total findings, auto-fixable, auto-fixed)
  - Historical SLO percentage calculation
  - Summary statistics via CLI

- **CLI Commands**
  - `scan-and-fix` - Main workflow command
  - `list-findings` - View open vulnerabilities
  - `show-slo` - Display SLO metrics
  - `smoke-test` - Verify deployment rollout
  - `--dry-run` mode for safe previews
  - `--severity` filtering

- **Docker Support**
  - Multi-stage Dockerfile
  - Non-root user execution
  - GitHub CLI pre-installed

### Technical Details

- Python 3.11+ required
- Type hints throughout codebase
- Dataclass-based models
- Modular architecture (dojo_client, fixer, git_client, slo_tracker)

---

[0.1.0]: https://github.com/jamilshaikh07/autofix-dojo/releases/tag/v0.1.0
