"""Kubernetes controller for AutofixPolicy CRD."""

import argparse
import asyncio
import logging
import os
import signal
import sys
from datetime import datetime, timezone
from typing import Any

from aiohttp import web
from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Prometheus metrics
RECONCILE_TOTAL = Counter(
    "autofix_reconcile_total",
    "Total number of reconciliation attempts",
    ["policy", "status"],
)
VULNERABILITIES_FOUND = Gauge(
    "autofix_vulnerabilities_found",
    "Number of vulnerabilities found",
    ["policy", "severity"],
)
HELM_CHARTS_OUTDATED = Gauge(
    "autofix_helm_charts_outdated",
    "Number of outdated Helm charts",
    ["policy", "priority"],
)
SLO_PERCENTAGE = Gauge(
    "autofix_slo_percentage",
    "Current SLO percentage",
    ["policy"],
)
LAST_SCAN_TIMESTAMP = Gauge(
    "autofix_last_scan_timestamp",
    "Timestamp of last scan",
    ["policy"],
)


class AutofixController:
    """Controller that watches AutofixPolicy CRDs and reconciles state."""

    def __init__(self, reconcile_interval: int = 60):
        self.reconcile_interval = reconcile_interval
        self.running = False
        self.policies: dict[str, dict[str, Any]] = {}
        self._shutdown_event = asyncio.Event()

    async def start(self) -> None:
        """Start the controller."""
        logger.info("Starting autofix-dojo controller")
        self.running = True

        # Start reconciliation loop
        reconcile_task = asyncio.create_task(self._reconcile_loop())

        # Wait for shutdown
        await self._shutdown_event.wait()

        # Cleanup
        reconcile_task.cancel()
        try:
            await reconcile_task
        except asyncio.CancelledError:
            pass

        logger.info("Controller stopped")

    def stop(self) -> None:
        """Stop the controller."""
        logger.info("Stopping controller...")
        self.running = False
        self._shutdown_event.set()

    async def _reconcile_loop(self) -> None:
        """Main reconciliation loop."""
        while self.running:
            try:
                await self._reconcile_all_policies()
            except Exception as e:
                logger.error(f"Error during reconciliation: {e}")

            await asyncio.sleep(self.reconcile_interval)

    async def _reconcile_all_policies(self) -> None:
        """Reconcile all AutofixPolicy resources."""
        logger.info("Starting reconciliation cycle")

        try:
            # In a real implementation, this would use the kubernetes client
            # to list AutofixPolicy resources and reconcile each one
            # For now, this is a placeholder that demonstrates the pattern
            await self._mock_reconcile()
        except Exception as e:
            logger.error(f"Reconciliation failed: {e}")
            raise

    async def _mock_reconcile(self) -> None:
        """Mock reconciliation for demonstration."""
        # This would be replaced with actual K8s API calls
        logger.info("Reconciliation complete (mock)")


class HealthServer:
    """HTTP server for health checks and metrics."""

    def __init__(self, controller: AutofixController, port: int = 8081):
        self.controller = controller
        self.port = port
        self.app = web.Application()
        self.app.router.add_get("/healthz", self.healthz)
        self.app.router.add_get("/readyz", self.readyz)
        self.app.router.add_get("/metrics", self.metrics)

    async def healthz(self, request: web.Request) -> web.Response:
        """Liveness probe endpoint."""
        return web.Response(text="ok")

    async def readyz(self, request: web.Request) -> web.Response:
        """Readiness probe endpoint."""
        if self.controller.running:
            return web.Response(text="ok")
        return web.Response(text="not ready", status=503)

    async def metrics(self, request: web.Request) -> web.Response:
        """Prometheus metrics endpoint."""
        return web.Response(
            body=generate_latest(),
            content_type=CONTENT_TYPE_LATEST,
        )

    async def start(self) -> web.AppRunner:
        """Start the health server."""
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", self.port)
        await site.start()
        logger.info(f"Health server listening on port {self.port}")
        return runner


async def main_async(args: argparse.Namespace) -> None:
    """Async main entry point."""
    controller = AutofixController(
        reconcile_interval=int(args.reconcile_interval.rstrip("s"))
    )

    # Setup signal handlers
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, controller.stop)

    # Start health server
    health_server = HealthServer(controller)
    runner = await health_server.start()

    try:
        # Start controller
        await controller.start()
    finally:
        # Cleanup
        await runner.cleanup()


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="autofix-dojo controller")
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Watch for AutofixPolicy changes",
    )
    parser.add_argument(
        "--reconcile-interval",
        default="60s",
        help="Reconciliation interval (default: 60s)",
    )
    parser.add_argument(
        "--health-port",
        type=int,
        default=8081,
        help="Health check port (default: 8081)",
    )
    parser.add_argument(
        "--metrics-port",
        type=int,
        default=8080,
        help="Metrics port (default: 8080)",
    )

    args = parser.parse_args()

    logger.info("=" * 50)
    logger.info("autofix-dojo Controller v0.2.0")
    logger.info("=" * 50)
    logger.info(f"Reconcile interval: {args.reconcile_interval}")
    logger.info(f"Health port: {args.health_port}")

    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
