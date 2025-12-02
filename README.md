# Autofix-Dojo

Autonomous vulnerability remediation service that integrates DefectDojo with Kubernetes deployments. It fetches HIGH/CRITICAL vulnerabilities, suggests safe image version bumps, and automatically creates pull requests to update your Kubernetes manifests or Helm values.

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐     ┌─────────┐
│ DefectDojo  │────▶│ Autofix-Dojo │────▶│  Git Repo   │────▶│ Argo CD │
│  (Scanner)  │     │   (Fixer)    │     │  (PR/MR)    │     │ (Deploy)│
└─────────────┘     └──────────────┘     └─────────────┘     └─────────┘
```

1. **DefectDojo** stores vulnerability findings from your scanners
2. **Autofix-Dojo** fetches findings, determines safe fixes, creates branches and PRs
3. **Git** receives PRs with updated image tags in manifests
4. **Argo CD** syncs on merge and deploys the fixed versions

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

## Prerequisites

- Running DefectDojo instance with API access
- Local clone of your Kubernetes manifests / Helm charts repo
- Python 3.11+ or Docker
- `gh` (GitHub CLI) or `glab` (GitLab CLI) authenticated

## Quick Start

```bash
# Clone and setup
cd autofix-dojo
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your values (see Configuration section)

# Seed DefectDojo with test data (optional)
python scripts/seed_dojo.py

# List findings
python -m autofix.cli list-findings

# Dry run
python -m autofix.cli scan-and-fix --dry-run

# Create PRs
python -m autofix.cli scan-and-fix

# View SLO
python -m autofix.cli show-slo
```

## Configuration

Create a `.env` file with the following:

```bash
# DefectDojo Configuration
DEFECTDOJO_URL=http://localhost:8080
DEFECTDOJO_API_KEY=your-api-key-here
DEFECTDOJO_PRODUCT_ID=1

# Git Configuration
GIT_REPO_PATH=/path/to/your/gitops-repo
GIT_REMOTE=origin
GIT_MAIN_BRANCH=main  # or master
GIT_PLATFORM=github   # or gitlab

# Argo CD (optional)
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

## Usage

### Scan and Fix
```bash
# Full run - fetch findings, create PRs
python -m autofix.cli scan-and-fix

# Dry run - see what would happen
python -m autofix.cli scan-and-fix --dry-run

# Filter severity
python -m autofix.cli scan-and-fix -s Critical
```

### View SLO Metrics
```bash
python -m autofix.cli show-slo
```

Output:
```
==================================================
📊 Vulnerability SLO Summary
==================================================
Total runs:              1
Total findings processed: 4
Total auto-fixed:         1
Average SLO:              25.0%
Latest SLO:               25.0%

📈 Recent Runs:
  2025-12-02T16:35:55: 1/4 fixed (25.0%)
```

### List Findings
```bash
python -m autofix.cli list-findings
python -m autofix.cli list-findings -s Critical -l 10
```

Output:
```
Found 4 open findings:

🔴 [Critical] CVE-2024-1234: Buffer Overflow in Traefik/Whoami
   Image: traefik/whoami:latest
   ID: 1

🟠 [High] CVE-2024-5678: Nginx Security Vulnerability
   Image: nginx:1.23.1
   ID: 2
```

### Smoke Test Deployment
```bash
python -m autofix.cli smoke-test my-deployment -n my-namespace
```

## Docker

```bash
# Build
docker build -f docker/Dockerfile -t autofix-dojo .

# Run
docker run --rm \
  -v /path/to/manifests:/manifests \
  -v ~/.gitconfig:/home/autofix/.gitconfig:ro \
  -e DEFECTDOJO_URL=https://dojo.example.com \
  -e DEFECTDOJO_API_KEY=xxx \
  -e GIT_REPO_PATH=/manifests \
  autofix-dojo scan-and-fix
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

## Vulnerability SLO

The service tracks a simple SLO metric:

```
SLO % = (auto_fixed_findings / total_findings) * 100
```

This measures what percentage of HIGH/CRITICAL vulnerabilities were automatically remediated via PRs. Use `show-slo` to view historical trends.

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

## Extending

- **Cron job**: Run `scan-and-fix` on a schedule
- **Kubernetes CronJob**: Deploy in-cluster for periodic runs
- **Custom fix logic**: Extend `fixer.py` with registry lookups or policy rules
- **Registry Integration**: Query Docker Hub/ECR for actual latest patch versions
