"""CLI entrypoint for autofix-dojo."""

import logging
import subprocess
import sys

import typer

from .config import Config
from .dojo_client import DojoClient, group_findings_by_image
from .fixer import generate_fix_suggestions
from .git_client import GitClient, apply_fix
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


def main() -> None:
    """Main entrypoint."""
    app()


if __name__ == "__main__":
    main()
