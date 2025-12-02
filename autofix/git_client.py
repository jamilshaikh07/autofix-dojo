"""Git integration for creating branches, commits, and pull requests."""

import logging
import re
import subprocess
import uuid
from datetime import datetime
from pathlib import Path

from .config import Config
from .models import FixResult, FixSuggestion

logger = logging.getLogger(__name__)


class GitClient:
    """Client for Git operations and PR creation."""

    def __init__(self, config: Config):
        self.config = config
        self.repo_path = config.git_repo_path
        self.remote = config.git_remote
        self.main_branch = config.git_main_branch
        self.platform = config.git_platform

    def _run_git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        """Run a git command in the repo directory."""
        cmd = ["git", *args]
        logger.debug(f"Running: {' '.join(cmd)}")
        return subprocess.run(
            cmd,
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            check=check,
        )

    def _run_cli(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        """Run gh or glab CLI command."""
        cli = "gh" if self.platform == "github" else "glab"
        cmd = [cli, *args]
        logger.debug(f"Running: {' '.join(cmd)}")
        return subprocess.run(
            cmd,
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            check=check,
        )

    def ensure_clean_state(self) -> bool:
        """Ensure working directory is clean."""
        result = self._run_git("status", "--porcelain")
        if result.stdout.strip():
            logger.warning("Working directory has uncommitted changes")
            return False
        return True

    def checkout_main(self) -> None:
        """Checkout and update main branch."""
        self._run_git("checkout", self.main_branch)
        self._run_git("pull", self.remote, self.main_branch)

    def create_branch(self, prefix: str = "autofix") -> str:
        """Create a new branch for the fix."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        short_id = uuid.uuid4().hex[:8]
        branch_name = f"{prefix}/{timestamp}_{short_id}"

        self._run_git("checkout", "-b", branch_name)
        logger.info(f"Created branch: {branch_name}")
        return branch_name

    def update_manifests_for_image(
        self,
        old_image: str,
        new_image: str,
    ) -> list[str]:
        """
        Search and update Kubernetes manifests with new image tag.

        Args:
            old_image: Full old image reference (e.g., nginx:1.23.1)
            new_image: Full new image reference (e.g., nginx:1.23.4)

        Returns:
            List of files that were modified.
        """
        changed_files = []

        # File patterns to search
        patterns = ["*.yaml", "*.yml", "values*.yaml", "Chart.yaml"]

        for pattern in patterns:
            for file_path in self.repo_path.rglob(pattern):
                if self._update_file(file_path, old_image, new_image):
                    rel_path = str(file_path.relative_to(self.repo_path))
                    changed_files.append(rel_path)

        logger.info(f"Updated {len(changed_files)} files")
        return changed_files

    def _update_file(self, file_path: Path, old_image: str, new_image: str) -> bool:
        """Update image references in a single file."""
        try:
            content = file_path.read_text()
        except Exception as e:
            logger.warning(f"Could not read {file_path}: {e}")
            return False

        # Patterns to match image references
        patterns = [
            # Standard Kubernetes: image: nginx:1.23.1
            (rf'(image:\s*["\']?){re.escape(old_image)}(["\']?)', rf'\g<1>{new_image}\g<2>'),
            # Helm values: repository: nginx, tag: 1.23.1
            (rf'(tag:\s*["\']?){re.escape(old_image.split(":")[-1])}(["\']?)',
             rf'\g<1>{new_image.split(":")[-1]}\g<2>'),
        ]

        modified = False
        new_content = content

        for pattern, replacement in patterns:
            if re.search(pattern, new_content):
                new_content = re.sub(pattern, replacement, new_content)
                modified = True

        if modified:
            file_path.write_text(new_content)
            return True

        return False

    def commit_changes(self, files: list[str], message: str) -> bool:
        """Stage and commit changes."""
        if not files:
            return False

        for file in files:
            self._run_git("add", file)

        self._run_git("commit", "-m", message)
        logger.info(f"Committed changes: {message}")
        return True

    def push_branch(self, branch_name: str) -> bool:
        """Push branch to remote."""
        result = self._run_git("push", "-u", self.remote, branch_name, check=False)
        if result.returncode != 0:
            logger.error(f"Failed to push branch: {result.stderr}")
            return False
        logger.info(f"Pushed branch: {branch_name}")
        return True

    def create_pull_request(
        self,
        branch_name: str,
        title: str,
        body: str,
    ) -> str | None:
        """Create a pull request using gh/glab CLI."""
        if self.platform == "github":
            result = self._run_cli(
                "pr", "create",
                "--title", title,
                "--body", body,
                "--base", self.main_branch,
                "--head", branch_name,
                check=False,
            )
        else:  # gitlab
            result = self._run_cli(
                "mr", "create",
                "--title", title,
                "--description", body,
                "--target-branch", self.main_branch,
                "--source-branch", branch_name,
                "--remove-source-branch",
                check=False,
            )

        if result.returncode != 0:
            logger.error(f"Failed to create PR: {result.stderr}")
            return None

        # Extract PR URL from output
        pr_url = result.stdout.strip().split("\n")[-1]
        logger.info(f"Created PR: {pr_url}")
        return pr_url


def apply_fix(
    git_client: GitClient,
    suggestion: FixSuggestion,
) -> FixResult:
    """
    Apply a fix suggestion: create branch, update files, commit, push, and create PR.

    Args:
        git_client: GitClient instance
        suggestion: Fix suggestion to apply

    Returns:
        FixResult with details of what happened.
    """
    result = FixResult(suggestion=suggestion)

    try:
        # Ensure clean state
        if not git_client.ensure_clean_state():
            result.error = "Working directory not clean"
            return result

        # Checkout main and create new branch
        git_client.checkout_main()
        branch_name = git_client.create_branch()
        result.branch_name = branch_name

        # Update manifests
        old_image = suggestion.full_current_image
        new_image = suggestion.full_suggested_image

        changed_files = git_client.update_manifests_for_image(old_image, new_image)
        result.files_changed = changed_files

        if not changed_files:
            result.error = f"No manifests found referencing {old_image}"
            git_client.checkout_main()
            return result

        # Commit changes
        commit_msg = f"Auto-fix: bump {suggestion.current_image} from {suggestion.current_tag} to {suggestion.suggested_tag}\n\nVulnerability remediation for finding #{suggestion.finding_id}"
        git_client.commit_changes(changed_files, commit_msg)

        # Push branch
        if not git_client.push_branch(branch_name):
            result.error = "Failed to push branch"
            return result

        # Create PR
        pr_title = f"[Autofix] Bump {suggestion.current_image} to {suggestion.suggested_tag}"
        pr_body = f"""## Automated Vulnerability Fix

This PR was automatically generated by autofix-dojo.

### Changes
- **Image**: `{suggestion.current_image}`
- **Current version**: `{suggestion.current_tag}`
- **New version**: `{suggestion.suggested_tag}`
- **Finding ID**: #{suggestion.finding_id}
- **Confidence**: {suggestion.confidence}

### Reason
{suggestion.reason}

### Files Changed
{chr(10).join(f'- `{f}`' for f in changed_files)}

---
*Generated by [autofix-dojo](https://github.com/your-org/autofix-dojo)*
"""

        pr_url = git_client.create_pull_request(branch_name, pr_title, pr_body)
        result.pr_url = pr_url
        result.success = pr_url is not None

    except Exception as e:
        logger.exception(f"Error applying fix: {e}")
        result.error = str(e)

    finally:
        # Return to main branch
        try:
            git_client.checkout_main()
        except Exception:
            pass

    return result
