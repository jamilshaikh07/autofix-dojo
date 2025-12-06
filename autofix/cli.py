"""CLI entrypoint for autofix-dojo."""

import logging
import subprocess
import sys
from pathlib import Path

import typer

from .config import Config
from .dojo_client import DojoClient, group_findings_by_image
from .fixer import generate_fix_suggestions
from .git_client import GitClient, apply_fix
from .helm.scanner import HelmScanner
from .helm.roadmap import generate_roadmap
from .slo_tracker import SLOTracker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = typer.Typer(
    name="autofix-dojo",
    help="Autonomous Vulnerability Fixer for DefectDojo + Kubernetes",
)


@app.command()
def scan_and_fix(
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-n",
        help="Show what would be done without making changes",
    ),
    severity: list[str] = typer.Option(
        ["Critical", "High"],
        "--severity",
        "-s",
        help="Severity levels to process",
    ),
) -> None:
    """Fetch findings from DefectDojo, generate fixes, and create PRs."""
    try:
        config = Config.from_env()
    except ValueError as e:
        typer.echo(f"Configuration error: {e}", err=True)
        raise typer.Exit(1)

    typer.echo("🔍 Connecting to DefectDojo...")
    dojo_client = DojoClient(config)
    git_client = GitClient(config)
    slo_tracker = SLOTracker(config)

    # Fetch findings
    typer.echo(f"📥 Fetching open {', '.join(severity)} findings...")
    findings = dojo_client.fetch_open_findings(severity)

    if not findings:
        typer.echo("✅ No open findings found!")
        return

    typer.echo(f"Found {len(findings)} open findings")

    # Group by image
    grouped = group_findings_by_image(findings)
    typer.echo(f"Grouped into {len(grouped)} unique images/components")

    # Generate fix suggestions
    typer.echo("🔧 Generating fix suggestions...")
    suggestions = generate_fix_suggestions(findings)

    if not suggestions:
        typer.echo("⚠️  No auto-fixable vulnerabilities found")
        return

    typer.echo(f"Generated {len(suggestions)} fix suggestions:")
    for s in suggestions:
        typer.echo(f"  • {s.current_image}: {s.current_tag} → {s.suggested_tag}")

    if dry_run:
        typer.echo("\n🏃 Dry run mode - no changes made")
        return

    # Start SLO tracking
    slo_tracker.start_run(
        total_findings=len(findings),
        auto_fixable=len(suggestions),
    )

    # Apply fixes
    typer.echo("\n🚀 Applying fixes...")
    success_count = 0

    for suggestion in suggestions:
        typer.echo(f"\nProcessing: {suggestion.full_current_image}...")
        result = apply_fix(git_client, suggestion)

        if result.success:
            typer.echo(f"  ✅ PR created: {result.pr_url}")
            slo_tracker.record_fix(result.pr_url or "")
            success_count += 1
        else:
            typer.echo(f"  ❌ Failed: {result.error}")

    # Complete SLO tracking
    record = slo_tracker.complete_run()

    # Summary
    typer.echo("\n" + "=" * 50)
    typer.echo("📊 Summary")
    typer.echo("=" * 50)
    typer.echo(f"Total findings:    {len(findings)}")
    typer.echo(f"Auto-fixable:      {len(suggestions)}")
    typer.echo(f"Successfully fixed: {success_count}")
    if record:
        typer.echo(f"SLO:               {record.slo_percentage:.1f}%")


@app.command()
def show_slo() -> None:
    """Display SLO summary and statistics."""
    try:
        config = Config.from_env()
    except ValueError as e:
        typer.echo(f"Configuration error: {e}", err=True)
        raise typer.Exit(1)

    slo_tracker = SLOTracker(config)
    summary = slo_tracker.get_summary()

    typer.echo("=" * 50)
    typer.echo("📊 Vulnerability SLO Summary")
    typer.echo("=" * 50)
    typer.echo(f"Total runs:              {summary['total_runs']}")
    typer.echo(f"Total findings processed: {summary['total_findings_processed']}")
    typer.echo(f"Total auto-fixed:         {summary['total_auto_fixed']}")
    typer.echo(f"Average SLO:              {summary['average_slo']:.1f}%")
    typer.echo(f"Latest SLO:               {summary['latest_slo']:.1f}%")

    # Show recent history
    history = slo_tracker.get_history(5)
    if history:
        typer.echo("\n📈 Recent Runs:")
        for record in reversed(history):
            typer.echo(
                f"  {record.timestamp[:19]}: "
                f"{record.auto_fixed}/{record.total_findings} fixed "
                f"({record.slo_percentage:.1f}%)"
            )


@app.command()
def smoke_test(
    deployment: str = typer.Argument(..., help="Deployment name"),
    namespace: str = typer.Option("default", "--namespace", "-n", help="Kubernetes namespace"),
) -> None:
    """Run a smoke test to verify deployment rollout status."""
    typer.echo(f"🔄 Checking rollout status for {deployment} in {namespace}...")

    result = subprocess.run(
        ["kubectl", "rollout", "status", f"deploy/{deployment}", "-n", namespace],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        typer.echo(f"✅ Deployment {deployment} is healthy")
        typer.echo(result.stdout)
    else:
        typer.echo(f"❌ Deployment {deployment} rollout issue:")
        typer.echo(result.stderr or result.stdout)
        raise typer.Exit(1)


@app.command()
def list_findings(
    severity: list[str] = typer.Option(
        ["Critical", "High"],
        "--severity",
        "-s",
        help="Severity levels to filter",
    ),
    limit: int = typer.Option(20, "--limit", "-l", help="Max findings to show"),
) -> None:
    """List open findings from DefectDojo."""
    try:
        config = Config.from_env()
    except ValueError as e:
        typer.echo(f"Configuration error: {e}", err=True)
        raise typer.Exit(1)

    dojo_client = DojoClient(config)
    findings = dojo_client.fetch_open_findings(severity)

    if not findings:
        typer.echo("No open findings found")
        return

    typer.echo(f"Found {len(findings)} open findings:\n")

    for finding in findings[:limit]:
        severity_icon = "🔴" if finding.severity.value == "Critical" else "🟠"
        typer.echo(f"{severity_icon} [{finding.severity.value}] {finding.title}")
        if finding.image_tag:
            typer.echo(f"   Image: {finding.image_tag}")
        typer.echo(f"   ID: {finding.id}")
        typer.echo()

    if len(findings) > limit:
        typer.echo(f"... and {len(findings) - limit} more")


@app.command()
def scan_helm(
    path: str = typer.Argument(
        ".",
        help="Path to scan for Helm charts (Terraform or ArgoCD apps)",
    ),
    source_type: str = typer.Option(
        "auto",
        "--type",
        "-t",
        help="Source type: terraform, argocd, cluster, or auto (detect)",
    ),
    output: str = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file for markdown report",
    ),
    kubeconfig: str = typer.Option(
        None,
        "--kubeconfig",
        "-k",
        help="Path to kubeconfig for cluster scanning",
    ),
) -> None:
    """Scan for outdated Helm charts in Terraform, ArgoCD apps, or cluster."""
    scanner = HelmScanner()
    releases = []

    # Auto-detect source type
    if source_type == "auto":
        path_obj = Path(path)
        if any(path_obj.rglob("*.tf")):
            source_type = "terraform"
        elif any(path_obj.rglob("*.yaml")) or any(path_obj.rglob("*.yml")):
            source_type = "argocd"
        else:
            source_type = "cluster"

    if source_type == "terraform":
        typer.echo(f"🔍 Scanning Terraform files in {path}...")
        releases = scanner.scan_terraform_dir(path)
    elif source_type == "argocd":
        typer.echo(f"🔍 Scanning ArgoCD Application manifests in {path}...")
        releases = scanner.scan_argocd_apps(path)
    elif source_type == "cluster":
        typer.echo(f"🔍 Scanning Kubernetes cluster for Helm releases...")
        releases = scanner.scan_cluster(kubeconfig)

    if not releases:
        typer.echo("No helm_release resources found")
        return

    # Summary
    outdated = [r for r in releases if r.is_outdated]
    critical = [r for r in releases if r.priority == "critical"]
    major = [r for r in releases if r.priority == "major"]

    typer.echo(f"\n📊 Found {len(releases)} Helm releases:")
    typer.echo(f"   🔴 Critical: {len(critical)}")
    typer.echo(f"   🟠 Major:    {len(major)}")
    typer.echo(f"   🟡 Minor:    {len([r for r in releases if r.priority == 'minor'])}")
    typer.echo(f"   ✅ Current:  {len([r for r in releases if r.priority == 'current'])}")

    typer.echo("\n" + "=" * 70)
    typer.echo(f"{'Chart':<30} {'Current':<12} {'Latest':<12} {'Status':<10}")
    typer.echo("=" * 70)

    for r in sorted(releases, key=lambda x: (
        {"critical": 0, "major": 1, "minor": 2, "current": 3}[x.priority],
        x.name
    )):
        latest = r.latest_version or "?"
        typer.echo(f"{r.priority_emoji} {r.chart:<28} {r.current_version:<12} {latest:<12}")

    # Generate report
    if output:
        report = scanner.generate_report(releases)
        Path(output).write_text(report)
        typer.echo(f"\n📄 Report saved to {output}")

    # Show critical upgrade paths
    if critical:
        typer.echo("\n" + "=" * 70)
        typer.echo("🚨 CRITICAL UPGRADES REQUIRED")
        typer.echo("=" * 70)
        for r in critical:
            typer.echo(f"\n{r.chart}: {r.current_version} → {r.latest_version}")
            typer.echo(f"   Run: autofix-dojo helm-roadmap {r.chart} {r.current_version} {r.latest_version}")


@app.command()
def helm_roadmap(
    chart: str = typer.Argument(..., help="Helm chart name"),
    current: str = typer.Argument(..., help="Current version"),
    target: str = typer.Argument(..., help="Target version"),
    output: str = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file for markdown roadmap",
    ),
) -> None:
    """Generate upgrade roadmap for a Helm chart."""
    typer.echo(f"📋 Generating upgrade roadmap for {chart}...")
    typer.echo(f"   {current} → {target}")

    roadmap = generate_roadmap(chart, current, target)

    typer.echo(f"\n{'=' * 60}")
    typer.echo(f"📍 Upgrade Path: {len(roadmap.steps)} steps")
    typer.echo(f"⏱️  Estimated Time: {roadmap.estimated_time_minutes} minutes")
    typer.echo(f"⚠️  Breaking Changes: {roadmap.total_breaking_changes}")
    typer.echo(f"{'=' * 60}")

    # Show path
    path_str = " → ".join([current] + [s.to_version for s in roadmap.steps])
    typer.echo(f"\n{path_str}\n")

    for i, step in enumerate(roadmap.steps, 1):
        typer.echo(f"Step {i}: {step.from_version} → {step.to_version} [{step.risk_emoji} {step.risk.upper()}]")
        if step.breaking_changes:
            for bc in step.breaking_changes:
                typer.echo(f"   ⚠️  {bc}")
        if step.notes:
            typer.echo(f"   📝 {step.notes}")

    if output:
        Path(output).write_text(roadmap.to_markdown())
        typer.echo(f"\n📄 Roadmap saved to {output}")


@app.command()
def scan_images(
    kubeconfig: str = typer.Option(
        None,
        "--kubeconfig",
        "-k",
        help="Path to kubeconfig file",
    ),
    namespace: str = typer.Option(
        None,
        "--namespace",
        "-n",
        help="Namespace to scan (default: all)",
    ),
    output: str = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file for report",
    ),
) -> None:
    """Scan Kubernetes cluster for container images and versions."""
    import json
    import os

    typer.echo("🔍 Scanning cluster for container images...")

    # Build kubectl command
    cmd = ["kubectl", "get", "deployments,statefulsets,daemonsets"]
    if namespace:
        cmd.extend(["-n", namespace])
    else:
        cmd.append("-A")
    cmd.extend(["-o", "json"])

    env = os.environ.copy()
    if kubeconfig:
        env["KUBECONFIG"] = kubeconfig

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, env=env)
        data = json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        typer.echo(f"❌ Failed to get resources: {e.stderr}", err=True)
        raise typer.Exit(1)
    except json.JSONDecodeError as e:
        typer.echo(f"❌ Failed to parse response: {e}", err=True)
        raise typer.Exit(1)

    # Extract images
    images: dict[str, list[dict]] = {}
    for item in data.get("items", []):
        metadata = item.get("metadata", {})
        ns = metadata.get("namespace", "default")
        name = metadata.get("name", "unknown")
        kind = item.get("kind", "Unknown")

        containers = item.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
        for container in containers:
            image = container.get("image", "")
            if image:
                if image not in images:
                    images[image] = []
                images[image].append({
                    "namespace": ns,
                    "name": name,
                    "kind": kind,
                    "container": container.get("name", ""),
                })

    if not images:
        typer.echo("No container images found")
        return

    # Parse and categorize images
    typer.echo(f"\n📊 Found {len(images)} unique images across {sum(len(v) for v in images.values())} workloads")
    typer.echo("\n" + "=" * 80)
    typer.echo(f"{'Image':<60} {'Workloads':<10}")
    typer.echo("=" * 80)

    # Sort by number of workloads using the image
    for image, workloads in sorted(images.items(), key=lambda x: -len(x[1])):
        # Truncate long image names
        display_image = image if len(image) <= 58 else "..." + image[-55:]
        typer.echo(f"{display_image:<60} {len(workloads):<10}")

    # Show images that might need updates (with version tags)
    typer.echo("\n" + "=" * 80)
    typer.echo("🔎 Images with explicit version tags (potential update candidates):")
    typer.echo("=" * 80)

    import re
    version_pattern = re.compile(r":v?\d+\.\d+")

    for image in sorted(images.keys()):
        if version_pattern.search(image) and ":latest" not in image:
            # Parse image:tag
            parts = image.rsplit(":", 1)
            if len(parts) == 2:
                img_name, tag = parts
                workload_count = len(images[image])
                typer.echo(f"  {img_name}")
                typer.echo(f"    Current: {tag} (used by {workload_count} workload(s))")

    if output:
        report_lines = ["# Cluster Image Scan Report\n"]
        report_lines.append(f"Total unique images: {len(images)}\n")
        report_lines.append("| Image | Tag | Workloads |")
        report_lines.append("|-------|-----|-----------|")
        for image, workloads in sorted(images.items()):
            parts = image.rsplit(":", 1)
            img_name = parts[0]
            tag = parts[1] if len(parts) == 2 else "latest"
            report_lines.append(f"| {img_name} | {tag} | {len(workloads)} |")
        Path(output).write_text("\n".join(report_lines))
        typer.echo(f"\n📄 Report saved to {output}")


@app.command()
def version() -> None:
    """Show autofix-dojo version."""
    typer.echo("autofix-dojo v0.2.0")
    typer.echo("Autonomous Vulnerability & Helm Chart Fixer")
    typer.echo("https://github.com/jamilshaikh07/autofix-dojo")


def main() -> None:
    """Main entrypoint."""
    app()


if __name__ == "__main__":
    main()
