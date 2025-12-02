"""Configuration management via environment variables."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass
class Config:
    """Application configuration loaded from environment variables."""

    # DefectDojo settings
    defectdojo_url: str
    defectdojo_api_key: str
    defectdojo_product_id: int | None = None

    # Git settings
    git_repo_path: Path = Path(".")
    git_remote: str = "origin"
    git_main_branch: str = "main"
    git_platform: str = "github"  # "github" or "gitlab"

    # Argo CD settings
    argo_enabled: bool = False

    # SLO tracking
    slo_db_path: Path = Path("slo_data.json")

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        load_dotenv()

        defectdojo_url = os.getenv("DEFECTDOJO_URL")
        defectdojo_api_key = os.getenv("DEFECTDOJO_API_KEY")

        if not defectdojo_url or not defectdojo_api_key:
            raise ValueError(
                "DEFECTDOJO_URL and DEFECTDOJO_API_KEY must be set"
            )

        product_id_str = os.getenv("DEFECTDOJO_PRODUCT_ID")
        product_id = int(product_id_str) if product_id_str else None

        git_repo_path = os.getenv("GIT_REPO_PATH", ".")

        return cls(
            defectdojo_url=defectdojo_url.rstrip("/"),
            defectdojo_api_key=defectdojo_api_key,
            defectdojo_product_id=product_id,
            git_repo_path=Path(git_repo_path),
            git_remote=os.getenv("GIT_REMOTE", "origin"),
            git_main_branch=os.getenv("GIT_MAIN_BRANCH", "main"),
            git_platform=os.getenv("GIT_PLATFORM", "github").lower(),
            argo_enabled=os.getenv("ARGO_ENABLED", "false").lower() == "true",
            slo_db_path=Path(os.getenv("SLO_DB_PATH", "slo_data.json")),
        )
