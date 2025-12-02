"""SLO tracking for vulnerability remediation metrics."""

import json
import logging
from datetime import datetime
from pathlib import Path

from .config import Config
from .models import SLORecord

logger = logging.getLogger(__name__)


class SLOTracker:
    """Tracks vulnerability SLO metrics in a JSON file."""

    def __init__(self, config: Config):
        self.db_path = config.slo_db_path
        self._ensure_db()

    def _ensure_db(self) -> None:
        """Ensure the database file exists."""
        if not self.db_path.exists():
            self._save_data({"records": [], "current": None})

    def _load_data(self) -> dict:
        """Load data from JSON file."""
        try:
            return json.loads(self.db_path.read_text())
        except Exception:
            return {"records": [], "current": None}

    def _save_data(self, data: dict) -> None:
        """Save data to JSON file."""
        self.db_path.write_text(json.dumps(data, indent=2))

    def start_run(self, total_findings: int, auto_fixable: int) -> SLORecord:
        """Start a new tracking run."""
        record = SLORecord(
            timestamp=datetime.utcnow().isoformat(),
            total_findings=total_findings,
            auto_fixable=auto_fixable,
            auto_fixed=0,
            prs_created=[],
        )

        data = self._load_data()
        data["current"] = {
            "timestamp": record.timestamp,
            "total_findings": record.total_findings,
            "auto_fixable": record.auto_fixable,
            "auto_fixed": record.auto_fixed,
            "prs_created": record.prs_created,
        }
        self._save_data(data)

        logger.info(f"Started SLO tracking run: {record.timestamp}")
        return record

    def record_fix(self, pr_url: str) -> None:
        """Record a successful fix."""
        data = self._load_data()
        if data["current"]:
            data["current"]["auto_fixed"] += 1
            data["current"]["prs_created"].append(pr_url)
            self._save_data(data)

    def complete_run(self) -> SLORecord | None:
        """Complete the current run and archive it."""
        data = self._load_data()
        if not data["current"]:
            return None

        record = SLORecord(
            timestamp=data["current"]["timestamp"],
            total_findings=data["current"]["total_findings"],
            auto_fixable=data["current"]["auto_fixable"],
            auto_fixed=data["current"]["auto_fixed"],
            prs_created=data["current"]["prs_created"],
        )

        # Archive the record
        data["records"].append(data["current"])
        data["current"] = None
        self._save_data(data)

        logger.info(f"Completed SLO run: {record.slo_percentage:.1f}%")
        return record

    def get_current(self) -> SLORecord | None:
        """Get current in-progress run."""
        data = self._load_data()
        if not data["current"]:
            return None

        return SLORecord(
            timestamp=data["current"]["timestamp"],
            total_findings=data["current"]["total_findings"],
            auto_fixable=data["current"]["auto_fixable"],
            auto_fixed=data["current"]["auto_fixed"],
            prs_created=data["current"]["prs_created"],
        )

    def get_history(self, limit: int = 10) -> list[SLORecord]:
        """Get historical SLO records."""
        data = self._load_data()
        records = data.get("records", [])[-limit:]

        return [
            SLORecord(
                timestamp=r["timestamp"],
                total_findings=r["total_findings"],
                auto_fixable=r["auto_fixable"],
                auto_fixed=r["auto_fixed"],
                prs_created=r.get("prs_created", []),
            )
            for r in records
        ]

    def get_summary(self) -> dict:
        """Get overall SLO summary statistics."""
        data = self._load_data()
        records = data.get("records", [])

        if not records:
            return {
                "total_runs": 0,
                "total_findings_processed": 0,
                "total_auto_fixed": 0,
                "average_slo": 0.0,
                "latest_slo": 0.0,
            }

        total_findings = sum(r["total_findings"] for r in records)
        total_fixed = sum(r["auto_fixed"] for r in records)
        slo_values = [
            (r["auto_fixed"] / r["total_findings"] * 100) if r["total_findings"] > 0 else 100.0
            for r in records
        ]

        return {
            "total_runs": len(records),
            "total_findings_processed": total_findings,
            "total_auto_fixed": total_fixed,
            "average_slo": sum(slo_values) / len(slo_values) if slo_values else 0.0,
            "latest_slo": slo_values[-1] if slo_values else 0.0,
        }
