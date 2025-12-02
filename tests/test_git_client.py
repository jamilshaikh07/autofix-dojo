"""Tests for Git client."""

import tempfile
from pathlib import Path

import pytest

from autofix.config import Config
from autofix.git_client import GitClient


@pytest.fixture
def temp_repo(tmp_path: Path) -> Path:
    """Create a temporary directory simulating a repo."""
    manifests_dir = tmp_path / "manifests"
    manifests_dir.mkdir()

    # Create sample Kubernetes deployment
    deployment = manifests_dir / "deployment.yaml"
    deployment.write_text("""apiVersion: apps/v1
kind: Deployment
metadata:
  name: web
spec:
  template:
    spec:
      containers:
      - name: web
        image: nginx:1.23.1
        ports:
        - containerPort: 80
""")

    # Create sample Helm values
    values = manifests_dir / "values.yaml"
    values.write_text("""image:
  repository: nginx
  tag: 1.23.1
  pullPolicy: IfNotPresent
""")

    return tmp_path


@pytest.fixture
def config(temp_repo: Path) -> Config:
    """Create config pointing to temp repo."""
    return Config(
        defectdojo_url="https://example.com",
        defectdojo_api_key="test-key",
        git_repo_path=temp_repo,
    )


class TestGitClientManifestUpdate:
    """Tests for manifest update functionality."""

    def test_update_deployment_yaml(self, config: Config, temp_repo: Path):
        client = GitClient(config)

        changed = client.update_manifests_for_image(
            "nginx:1.23.1",
            "nginx:1.23.4",
        )

        assert len(changed) >= 1
        assert any("deployment.yaml" in f for f in changed)

        # Verify content was updated
        deployment = temp_repo / "manifests" / "deployment.yaml"
        content = deployment.read_text()
        assert "nginx:1.23.4" in content
        assert "nginx:1.23.1" not in content

    def test_update_helm_values(self, config: Config, temp_repo: Path):
        client = GitClient(config)

        changed = client.update_manifests_for_image(
            "nginx:1.23.1",
            "nginx:1.23.4",
        )

        # Verify values.yaml was updated
        values = temp_repo / "manifests" / "values.yaml"
        content = values.read_text()
        assert "tag: 1.23.4" in content

    def test_no_changes_for_missing_image(self, config: Config, temp_repo: Path):
        client = GitClient(config)

        changed = client.update_manifests_for_image(
            "redis:7.0.0",
            "redis:7.0.14",
        )

        assert len(changed) == 0
