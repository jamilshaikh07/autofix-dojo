"""Upgrade roadmap generator for Helm charts with breaking change detection."""

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class UpgradeStep:
    """A single step in an upgrade path."""

    from_version: str
    to_version: str
    breaking_changes: list[str] = field(default_factory=list)
    notes: str = ""
    risk: str = "low"  # low, medium, high

    @property
    def risk_emoji(self) -> str:
        return {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(self.risk, "⚪")


@dataclass
class UpgradeRoadmap:
    """Complete upgrade roadmap for a Helm chart."""

    chart: str
    current_version: str
    target_version: str
    steps: list[UpgradeStep] = field(default_factory=list)
    total_breaking_changes: int = 0
    estimated_time_minutes: int = 0

    def to_markdown(self) -> str:
        """Generate markdown documentation for the roadmap."""
        lines = [
            f"# Upgrade Roadmap: {self.chart}",
            "",
            f"**Current Version**: {self.current_version}",
            f"**Target Version**: {self.target_version}",
            f"**Total Steps**: {len(self.steps)}",
            f"**Estimated Time**: {self.estimated_time_minutes} minutes",
            "",
            "## Upgrade Path",
            "",
            "```",
            " → ".join([self.current_version] + [s.to_version for s in self.steps]),
            "```",
            "",
            "## Step-by-Step Guide",
            "",
        ]

        for i, step in enumerate(self.steps, 1):
            lines.append(f"### Step {i}: {step.from_version} → {step.to_version}")
            lines.append("")
            lines.append(f"**Risk Level**: {step.risk_emoji} {step.risk.upper()}")
            lines.append("")

            if step.breaking_changes:
                lines.append("**Breaking Changes**:")
                for bc in step.breaking_changes:
                    lines.append(f"- ⚠️ {bc}")
                lines.append("")

            if step.notes:
                lines.append(f"**Notes**: {step.notes}")
                lines.append("")

            lines.append("```bash")
            lines.append(f"helm upgrade {self.chart} <repo>/{self.chart} --version {step.to_version} \\")
            lines.append(f"  --namespace <namespace> \\")
            lines.append(f"  -f values-{step.to_version}.yaml")
            lines.append("```")
            lines.append("")

        return "\n".join(lines)


# Known breaking changes database
BREAKING_CHANGES_DB: dict[str, dict[str, dict[str, Any]]] = {
    "velero": {
        "5.0.0": {
            "breaking_changes": [
                "Requires DataUpload/DataDownload CRDs for v1.13+",
                "Configuration structure changes",
            ],
            "risk": "high",
            "notes": "Apply CRDs before upgrade",
        },
        "7.0.0": {
            "breaking_changes": [
                "CSI plugin merged into Velero core",
                "Remove velero-plugin-for-csi from initContainers",
            ],
            "risk": "high",
            "notes": "Critical if using CSI snapshots",
        },
        "9.0.0": {
            "breaking_changes": [
                "deployRestic renamed to deployNodeAgent",
                "Node-agent architecture changes",
            ],
            "risk": "medium",
            "notes": "Update values.yaml accordingly",
        },
        "11.0.0": {
            "breaking_changes": [
                "fs-backup modernized to micro-service architecture",
                "Optional migration from restic to kopia uploader",
            ],
            "risk": "medium",
            "notes": "Review fs-backup configuration",
        },
    },
    "grafana": {
        "10.0.0": {
            "breaking_changes": [
                "Angular deprecated - affects some plugins",
                "Dashboard JSON format changes",
                "New alerting system (Grafana Alerting v2)",
            ],
            "risk": "medium",
            "notes": "Test dashboards after upgrade",
        },
    },
    "sumologic": {
        "4.0.0": {
            "breaking_changes": [
                "New log collection architecture",
                "Fluent Bit replaces FluentD as default",
                "OpenTelemetry-based metrics collection",
                "New values.yaml structure",
            ],
            "risk": "high",
            "notes": "Significant configuration changes required",
        },
    },
    "cert-manager": {
        "1.12.0": {
            "breaking_changes": [
                "Webhook validation changes",
                "New CRD versions",
            ],
            "risk": "medium",
            "notes": "Apply CRDs before upgrade",
        },
    },
    "ingress-nginx": {
        "4.0.0": {
            "breaking_changes": [
                "Ingress API v1 required (networking.k8s.io/v1)",
                "Deprecated annotations removed",
            ],
            "risk": "high",
            "notes": "Update all Ingress resources to v1 API",
        },
    },
    "aws-load-balancer-controller": {
        "1.5.0": {
            "breaking_changes": [
                "TargetGroupBinding CRD v1beta1 → v1",
            ],
            "risk": "medium",
            "notes": "Review TargetGroupBinding resources",
        },
    },
}

# Recommended upgrade paths (version → next safe version)
UPGRADE_PATHS: dict[str, dict[str, str]] = {
    "velero": {
        "4.3.0": "5.4.1",
        "5.4.1": "6.7.0",
        "6.7.0": "7.2.2",
        "7.2.2": "8.7.2",
        "8.7.2": "10.1.3",
        "10.1.3": "11.2.0",
    },
    "grafana": {
        "9.2.10": "9.5.0",
        "9.5.0": "10.0.0",
        "10.0.0": "10.3.0",
    },
    "sumologic": {
        "3.19.5": "4.0.0",
        "4.0.0": "4.10.0",
        "4.10.0": "4.18.0",
    },
}


def generate_roadmap(
    chart: str,
    current_version: str,
    target_version: str,
) -> UpgradeRoadmap:
    """Generate an upgrade roadmap for a Helm chart."""
    roadmap = UpgradeRoadmap(
        chart=chart,
        current_version=current_version,
        target_version=target_version,
    )

    # Get upgrade path
    path = UPGRADE_PATHS.get(chart, {})
    breaking_changes = BREAKING_CHANGES_DB.get(chart, {})

    current = current_version
    while current != target_version:
        next_version = path.get(current)

        if not next_version:
            # Direct upgrade if no specific path defined
            next_version = target_version

        # Check for breaking changes in this step
        step_breaking_changes = []
        step_risk = "low"
        step_notes = ""

        # Check all versions between current and next for breaking changes
        for bc_version, bc_info in breaking_changes.items():
            if _version_in_range(bc_version, current, next_version):
                step_breaking_changes.extend(bc_info.get("breaking_changes", []))
                if bc_info.get("risk") == "high":
                    step_risk = "high"
                elif bc_info.get("risk") == "medium" and step_risk != "high":
                    step_risk = "medium"
                if bc_info.get("notes"):
                    step_notes = bc_info["notes"]

        step = UpgradeStep(
            from_version=current,
            to_version=next_version,
            breaking_changes=step_breaking_changes,
            notes=step_notes,
            risk=step_risk,
        )
        roadmap.steps.append(step)
        roadmap.total_breaking_changes += len(step_breaking_changes)

        current = next_version

        # Safety check to prevent infinite loops
        if len(roadmap.steps) > 20:
            logger.warning(f"Too many upgrade steps for {chart}, stopping")
            break

    # Estimate time (5 min base + 10 min per high-risk step + 5 min per breaking change)
    roadmap.estimated_time_minutes = 5 + sum(
        10 if s.risk == "high" else 5 for s in roadmap.steps
    ) + roadmap.total_breaking_changes * 2

    return roadmap


def _version_in_range(version: str, start: str, end: str) -> bool:
    """Check if a version is within a range (exclusive start, inclusive end)."""
    try:
        v = _parse_version(version)
        s = _parse_version(start)
        e = _parse_version(end)
        return s < v <= e
    except (ValueError, IndexError):
        return False


def _parse_version(version: str) -> tuple[int, ...]:
    """Parse a version string into a tuple of integers."""
    clean = version.lstrip("v").split("-")[0]
    return tuple(int(x) for x in clean.split("."))
