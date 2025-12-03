# autofix-dojo

> Autonomous vulnerability remediation for Kubernetes. Fix CVEs while you sleep.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![DefectDojo](https://img.shields.io/badge/DefectDojo-Compatible-green.svg)](https://www.defectdojo.com/)

**autofix-dojo** connects to your DefectDojo instance, identifies vulnerable container images, bumps them to patched versions, and opens pull requests automatically. It's your first step toward autonomous InfraOps.

## Features

- **DefectDojo Integration** - Fetch Critical/High findings via REST API
- **Smart Image Versioning** - Suggests safe patch-level updates using semver logic
- **Kubernetes-Native** - Updates Deployments, Helm values, and YAML manifests
- **Git Automation** - Creates branches, commits, and PRs via `gh`/`glab` CLI
- **SLO Tracking** - Measures auto-fix success rate over time
- **Dry-Run Mode** - Preview changes without modifying anything
- **GitHub & GitLab Support** - Works with both platforms out of the box

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   DefectDojo    │────▶│   autofix-dojo   │────▶│   Git (GitHub/  │
│   (Findings)    │     │                  │     │     GitLab)     │
└─────────────────┘     └────────┬─────────┘     └────────┬────────┘
                                 │                        │
                                 │                        ▼
                        ┌────────▼─────────┐     ┌─────────────────┐
                        │  K8s Manifests/  │     │     ArgoCD      │
                        │   Helm Values    │     │   (GitOps Sync) │
                        └──────────────────┘     └─────────────────┘
```

## How It Works

1. **Fetch** - Queries DefectDojo API for open Critical/High vulnerabilities
2. **Analyze** - Groups findings by container image and determines fix candidates
3. **Suggest** - Uses known-safe mappings or semver patch bumps to suggest updates
4. **Update** - Modifies Kubernetes manifests and Helm values in your GitOps repo
5. **PR** - Creates a pull request with detailed change summary
6. **Track** - Records SLO metrics for compliance reporting

## Working Demo

Successfully tested against a homelab Kubernetes cluster:

- **PR Created**: [talos-proxmox-gitops#3](https://github.com/jamilshaikh07/talos-proxmox-gitops/pull/3)
- **Fix Applied**: `nginx:1.23.1` → `nginx:1.23.4`
- **SLO Tracked**: 25% (1 of 4 findings auto-fixed)

### Sample Output

```
🔍 Connecting to DefectDojo...
📥 Fetching open Critical, High findings...
Found 4 open findings
Grouped into 4 unique images/components
🔧 Generating fix suggestions...
Generated 3 fix suggestions:
  • nginx: 1.23.1 → 1.23.4
  • redis: 7.0.0 → 7.0.14
  • python: 3.11.0 → 3.11.7

🚀 Applying fixes...
Processing: nginx:1.23.1...
  ✅ PR created: https://github.com/jamilshaikh07/talos-proxmox-gitops/pull/3

==================================================
📊 Summary
==================================================
Total findings:    4
Auto-fixable:      3
Successfully fixed: 1
SLO:               25.0%
```

## Quick Start

```bash
# Clone the repository
git clone https://github.com/jamilshaikh07/autofix-dojo.git
cd autofix-dojo

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your values

# Seed DefectDojo with test data (optional)
python scripts/seed_dojo.py

# Run in dry-run mode first
python -m autofix.cli scan-and-fix --dry-run

# Run for real
python -m autofix.cli scan-and-fix
```

## Requirements

- Python 3.11+
- Git
- GitHub CLI (`gh`) or GitLab CLI (`glab`)
- Access to a DefectDojo instance
- A GitOps repository with Kubernetes manifests

## Configuration

Create a `.env` file or set environment variables:

```bash
# DefectDojo
DEFECTDOJO_URL=https://defectdojo.example.com
DEFECTDOJO_API_KEY=your-api-key-here
DEFECTDOJO_PRODUCT_ID=1

# Git
GIT_REPO_PATH=/path/to/your/k8s-manifests
GIT_REMOTE=origin
GIT_MAIN_BRANCH=main
GIT_PLATFORM=github  # or gitlab

# ArgoCD (optional)
ARGO_ENABLED=false

# SLO Tracking
SLO_DB_PATH=slo_data.json
```

### Getting a DefectDojo API Key

```bash
# If using Docker Compose DefectDojo
docker exec django-defectdojo-uwsgi-1 python /app/manage.py shell -c "
from dojo.models import Dojo_User
from rest_framework.authtoken.models import Token
user = Dojo_User.objects.get(username='admin')
token, created = Token.objects.get_or_create(user=user)
print(f'API_KEY={token.key}')
"
```

## CLI Commands

```bash
# Scan and auto-fix vulnerabilities
python -m autofix.cli scan-and-fix
python -m autofix.cli scan-and-fix --dry-run
python -m autofix.cli scan-and-fix --severity Critical

# List open findings
python -m autofix.cli list-findings
python -m autofix.cli list-findings --severity Critical --limit 50

# View SLO metrics
python -m autofix.cli show-slo

# Smoke test a deployment
python -m autofix.cli smoke-test my-deployment -n my-namespace
```

## Docker

```bash
# Build
docker build -t autofix-dojo -f docker/Dockerfile .

# Run
docker run --rm \
  -v /path/to/manifests:/manifests \
  -v ~/.gitconfig:/home/autofix/.gitconfig:ro \
  -e DEFECTDOJO_URL=https://dojo.example.com \
  -e DEFECTDOJO_API_KEY=xxx \
  -e GIT_REPO_PATH=/manifests \
  autofix-dojo scan-and-fix --dry-run
```

## Project Structure

```
autofix-dojo/
├── autofix/
│   ├── __init__.py
│   ├── cli.py           # Typer CLI commands
│   ├── config.py        # Environment variable loading
│   ├── dojo_client.py   # DefectDojo REST API client
│   ├── fixer.py         # Version parsing and fix suggestions
│   ├── git_client.py    # Git operations and PR creation
│   ├── models.py        # Dataclasses (Finding, FixSuggestion, etc.)
│   └── slo_tracker.py   # JSON-based SLO tracking
├── scripts/
│   └── seed_dojo.py     # Seed DefectDojo with test data
├── tests/
├── docker/
│   └── Dockerfile
├── .env.example
├── requirements.txt
└── README.md
```

## Known Safe Versions

The fixer includes mappings for common images:

| Image | Vulnerable Versions | Safe Version |
|-------|---------------------|--------------|
| nginx | 1.23.1, 1.23.2, 1.23.3 | 1.23.4 |
| python | 3.9.0, 3.10.0, 3.11.0 | 3.9.18, 3.10.13, 3.11.7 |
| redis | 7.0.0, 7.2.0 | 7.0.14, 7.2.4 |
| postgres | 15.0, 16.0 | 15.5, 16.1 |
| node | 18.0.0, 20.0.0 | 18.19.0, 20.10.0 |

For unknown versions, the fixer increments the patch version by 3.

## Vulnerability SLO

The service tracks a simple SLO metric:

```
SLO % = (auto_fixed_findings / total_findings) * 100
```

This measures what percentage of HIGH/CRITICAL vulnerabilities were automatically remediated via PRs. Use `show-slo` to view historical trends.

## Roadmap

See [ROADMAP.md](ROADMAP.md) for the full vision.

| Version | Milestone |
|---------|-----------|
| v0.1 | MVP - DefectDojo + GitHub PRs |
| v0.2 | Improved fixer logic, registry lookups |
| v0.3 | GitLab MR support |
| v0.4 | ArgoCD sync integration |
| v0.5 | Kubernetes CronJob mode |
| v1.0 | InfraOps Autonomous Engine |

## Why Open Source?

Security automation shouldn't be locked behind enterprise paywalls. By open-sourcing autofix-dojo, we aim to:

- Give every team access to vulnerability auto-remediation
- Build a community around autonomous InfraOps
- Learn from real-world usage patterns
- Accelerate the path to fully autonomous infrastructure

## Screenshots

<!-- TODO: Add screenshots -->
![Dashboard](docs/images/dashboard-placeholder.png)
*DefectDojo findings list*

![PR Example](docs/images/pr-placeholder.png)
*Auto-generated pull request*

![SLO Report](docs/images/slo-placeholder.png)
*SLO tracking output*

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.

---
