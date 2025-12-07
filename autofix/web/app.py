"""FastAPI web application for autofix-dojo dashboard."""

import json
import os
import subprocess
import time
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(
    title="autofix-dojo",
    description="Autonomous Vulnerability Remediation & Helm Chart Upgrade Operator",
    version="0.2.0",
)


class JobTriggerRequest(BaseModel):
    """Request to trigger a job."""
    job_type: str
    namespace: str = "autofix-dojo"


class JobStatus(BaseModel):
    """Job status response."""
    name: str
    status: str
    start_time: Optional[str] = None
    completion_time: Optional[str] = None
    duration: Optional[str] = None


def run_kubectl(args: list[str], timeout: int = 30) -> tuple[int, str, str]:
    """Run kubectl command and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            ["kubectl"] + args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 1, "", "Command timed out"
    except Exception as e:
        return 1, "", str(e)


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Render the main dashboard."""
    return HTML_TEMPLATE


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.get("/api/cronjobs")
async def list_cronjobs(namespace: str = "autofix-dojo"):
    """List all autofix-dojo CronJobs."""
    code, stdout, stderr = run_kubectl([
        "get", "cronjobs", "-n", namespace,
        "-l", "app.kubernetes.io/name=autofix-dojo",
        "-o", "json"
    ])

    if code != 0:
        # Try without label filter
        code, stdout, stderr = run_kubectl([
            "get", "cronjobs", "-n", namespace, "-o", "json"
        ])

    if code != 0:
        raise HTTPException(status_code=500, detail=f"Failed to list cronjobs: {stderr}")

    try:
        data = json.loads(stdout)
        cronjobs = []
        for item in data.get("items", []):
            metadata = item.get("metadata", {})
            spec = item.get("spec", {})
            status = item.get("status", {})

            cronjobs.append({
                "name": metadata.get("name", ""),
                "schedule": spec.get("schedule", ""),
                "suspend": spec.get("suspend", False),
                "last_schedule": status.get("lastScheduleTime"),
                "active": len(status.get("active", [])),
            })
        return {"cronjobs": cronjobs}
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Failed to parse cronjob data")


@app.get("/api/jobs")
async def list_jobs(namespace: str = "autofix-dojo", limit: int = 10):
    """List recent jobs."""
    code, stdout, stderr = run_kubectl([
        "get", "jobs", "-n", namespace,
        "--sort-by=.metadata.creationTimestamp",
        "-o", "json"
    ])

    if code != 0:
        raise HTTPException(status_code=500, detail=f"Failed to list jobs: {stderr}")

    try:
        data = json.loads(stdout)
        jobs = []
        for item in data.get("items", [])[-limit:]:
            metadata = item.get("metadata", {})
            status = item.get("status", {})

            # Determine job status
            conditions = status.get("conditions", [])
            job_status = "Running"
            for cond in conditions:
                if cond.get("type") == "Complete" and cond.get("status") == "True":
                    job_status = "Completed"
                elif cond.get("type") == "Failed" and cond.get("status") == "True":
                    job_status = "Failed"

            if status.get("active", 0) > 0:
                job_status = "Running"

            jobs.append({
                "name": metadata.get("name", ""),
                "status": job_status,
                "start_time": status.get("startTime"),
                "completion_time": status.get("completionTime"),
                "succeeded": status.get("succeeded", 0),
                "failed": status.get("failed", 0),
            })

        # Reverse to show newest first
        jobs.reverse()
        return {"jobs": jobs}
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Failed to parse job data")


@app.post("/api/trigger")
async def trigger_job(request: JobTriggerRequest):
    """Trigger a job from a CronJob."""
    cronjob_map = {
        "helm-upgrade-pr": "autofix-dojo-helm-upgrade-pr",
        "helm-scan": "autofix-dojo-helm-scan",
        "vuln-scan": "autofix-dojo-vuln-scan",
    }

    if request.job_type not in cronjob_map:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid job type. Valid types: {', '.join(cronjob_map.keys())}"
        )

    cronjob_name = cronjob_map[request.job_type]
    job_name = f"{request.job_type}-manual-{int(time.time())}"

    # Check if cronjob exists
    code, _, stderr = run_kubectl([
        "get", "cronjob", cronjob_name, "-n", request.namespace
    ])

    if code != 0:
        raise HTTPException(
            status_code=404,
            detail=f"CronJob '{cronjob_name}' not found in namespace '{request.namespace}'"
        )

    # Create job
    code, stdout, stderr = run_kubectl([
        "create", "job", f"--from=cronjob/{cronjob_name}",
        job_name, "-n", request.namespace
    ])

    if code != 0:
        raise HTTPException(status_code=500, detail=f"Failed to create job: {stderr}")

    return {
        "message": f"Job '{job_name}' created successfully",
        "job_name": job_name,
        "namespace": request.namespace,
    }


@app.get("/api/job/{job_name}/logs")
async def get_job_logs(job_name: str, namespace: str = "autofix-dojo", tail: int = 100):
    """Get logs for a job."""
    code, stdout, stderr = run_kubectl([
        "logs", f"job/{job_name}", "-n", namespace,
        "--all-containers", f"--tail={tail}"
    ])

    if code != 0:
        raise HTTPException(status_code=500, detail=f"Failed to get logs: {stderr}")

    return {"logs": stdout}


@app.delete("/api/job/{job_name}")
async def delete_job(job_name: str, namespace: str = "autofix-dojo"):
    """Delete a job."""
    code, _, stderr = run_kubectl([
        "delete", "job", job_name, "-n", namespace
    ])

    if code != 0:
        raise HTTPException(status_code=500, detail=f"Failed to delete job: {stderr}")

    return {"message": f"Job '{job_name}' deleted"}


@app.get("/api/helm/releases")
async def scan_helm_releases(path: str = "/repo/gitops/apps"):
    """Scan for Helm releases and check for updates."""
    from autofix.helm.scanner import HelmScanner

    scanner = HelmScanner()
    try:
        releases = scanner.scan_argocd_apps(path)

        result = []
        for r in releases:
            result.append({
                "name": r.name,
                "chart": r.chart,
                "current_version": r.current_version,
                "latest_version": r.latest_version,
                "is_outdated": r.is_outdated,
                "priority": r.priority,
                "priority_emoji": r.priority_emoji,
                "namespace": r.namespace,
                "source_file": r.source_file,
            })

        return {"releases": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# HTML Template - embedded for simplicity
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>autofix-dojo Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
    <style>
        .loading { opacity: 0.5; pointer-events: none; }
        @keyframes spin { to { transform: rotate(360deg); } }
        .spinner { animation: spin 1s linear infinite; }
    </style>
</head>
<body class="bg-gray-900 text-gray-100 min-h-screen">
    <nav class="bg-gray-800 border-b border-gray-700 px-6 py-4">
        <div class="flex items-center justify-between max-w-7xl mx-auto">
            <div class="flex items-center space-x-3">
                <span class="text-2xl">🥋</span>
                <h1 class="text-xl font-bold">autofix-dojo</h1>
            </div>
            <div class="text-sm text-gray-400">
                Autonomous Vulnerability & Helm Chart Fixer
            </div>
        </div>
    </nav>

    <main class="max-w-7xl mx-auto px-6 py-8">
        <!-- Quick Actions -->
        <section class="mb-8">
            <h2 class="text-lg font-semibold mb-4 flex items-center">
                <span class="mr-2">🚀</span> Quick Actions
            </h2>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                <button onclick="triggerJob('helm-upgrade-pr')"
                    class="bg-blue-600 hover:bg-blue-700 px-6 py-4 rounded-lg text-left transition">
                    <div class="font-semibold">Helm Upgrade PRs</div>
                    <div class="text-sm text-blue-200">Scan & create upgrade PRs</div>
                </button>
                <button onclick="triggerJob('helm-scan')"
                    class="bg-purple-600 hover:bg-purple-700 px-6 py-4 rounded-lg text-left transition">
                    <div class="font-semibold">Helm Scan</div>
                    <div class="text-sm text-purple-200">Scan for chart drift</div>
                </button>
                <button onclick="triggerJob('vuln-scan')"
                    class="bg-red-600 hover:bg-red-700 px-6 py-4 rounded-lg text-left transition">
                    <div class="font-semibold">Vulnerability Scan</div>
                    <div class="text-sm text-red-200">Scan for vulnerabilities</div>
                </button>
            </div>
        </section>

        <!-- CronJobs -->
        <section class="mb-8">
            <div class="flex items-center justify-between mb-4">
                <h2 class="text-lg font-semibold flex items-center">
                    <span class="mr-2">⏰</span> Scheduled Jobs
                </h2>
                <button onclick="loadCronJobs()" class="text-sm text-blue-400 hover:text-blue-300">
                    Refresh
                </button>
            </div>
            <div id="cronjobs" class="bg-gray-800 rounded-lg overflow-hidden">
                <div class="p-4 text-gray-400">Loading...</div>
            </div>
        </section>

        <!-- Recent Jobs -->
        <section class="mb-8">
            <div class="flex items-center justify-between mb-4">
                <h2 class="text-lg font-semibold flex items-center">
                    <span class="mr-2">📋</span> Recent Jobs
                </h2>
                <button onclick="loadJobs()" class="text-sm text-blue-400 hover:text-blue-300">
                    Refresh
                </button>
            </div>
            <div id="jobs" class="bg-gray-800 rounded-lg overflow-hidden">
                <div class="p-4 text-gray-400">Loading...</div>
            </div>
        </section>

        <!-- Logs Modal -->
        <div id="logsModal" class="fixed inset-0 bg-black bg-opacity-50 hidden items-center justify-center z-50">
            <div class="bg-gray-800 rounded-lg w-full max-w-4xl max-h-[80vh] m-4 flex flex-col">
                <div class="flex items-center justify-between p-4 border-b border-gray-700">
                    <h3 id="logsTitle" class="font-semibold">Job Logs</h3>
                    <button onclick="closeLogsModal()" class="text-gray-400 hover:text-white">✕</button>
                </div>
                <div id="logsContent" class="flex-1 overflow-auto p-4">
                    <pre class="text-sm text-gray-300 whitespace-pre-wrap font-mono"></pre>
                </div>
            </div>
        </div>
    </main>

    <script>
        const namespace = 'autofix-dojo';

        async function loadCronJobs() {
            const container = document.getElementById('cronjobs');
            container.innerHTML = '<div class="p-4 text-gray-400">Loading...</div>';

            try {
                const res = await fetch(`/api/cronjobs?namespace=${namespace}`);
                const data = await res.json();

                if (data.cronjobs.length === 0) {
                    container.innerHTML = '<div class="p-4 text-gray-400">No CronJobs found</div>';
                    return;
                }

                let html = '<table class="w-full"><thead class="bg-gray-700"><tr>' +
                    '<th class="px-4 py-3 text-left text-sm">Name</th>' +
                    '<th class="px-4 py-3 text-left text-sm">Schedule</th>' +
                    '<th class="px-4 py-3 text-left text-sm">Last Run</th>' +
                    '<th class="px-4 py-3 text-left text-sm">Status</th>' +
                    '</tr></thead><tbody>';

                for (const cj of data.cronjobs) {
                    const lastRun = cj.last_schedule ? new Date(cj.last_schedule).toLocaleString() : 'Never';
                    const status = cj.suspend ?
                        '<span class="text-yellow-400">Suspended</span>' :
                        (cj.active > 0 ? '<span class="text-blue-400">Running</span>' : '<span class="text-green-400">Active</span>');

                    html += `<tr class="border-t border-gray-700 hover:bg-gray-750">
                        <td class="px-4 py-3 font-mono text-sm">${cj.name}</td>
                        <td class="px-4 py-3 text-sm text-gray-400">${cj.schedule}</td>
                        <td class="px-4 py-3 text-sm text-gray-400">${lastRun}</td>
                        <td class="px-4 py-3 text-sm">${status}</td>
                    </tr>`;
                }

                html += '</tbody></table>';
                container.innerHTML = html;
            } catch (err) {
                container.innerHTML = `<div class="p-4 text-red-400">Error: ${err.message}</div>`;
            }
        }

        async function loadJobs() {
            const container = document.getElementById('jobs');
            container.innerHTML = '<div class="p-4 text-gray-400">Loading...</div>';

            try {
                const res = await fetch(`/api/jobs?namespace=${namespace}&limit=10`);
                const data = await res.json();

                if (data.jobs.length === 0) {
                    container.innerHTML = '<div class="p-4 text-gray-400">No jobs found</div>';
                    return;
                }

                let html = '<table class="w-full"><thead class="bg-gray-700"><tr>' +
                    '<th class="px-4 py-3 text-left text-sm">Name</th>' +
                    '<th class="px-4 py-3 text-left text-sm">Status</th>' +
                    '<th class="px-4 py-3 text-left text-sm">Started</th>' +
                    '<th class="px-4 py-3 text-left text-sm">Actions</th>' +
                    '</tr></thead><tbody>';

                for (const job of data.jobs) {
                    const started = job.start_time ? new Date(job.start_time).toLocaleString() : '-';
                    let statusClass = 'text-gray-400';
                    let statusIcon = '⏳';

                    if (job.status === 'Completed') {
                        statusClass = 'text-green-400';
                        statusIcon = '✅';
                    } else if (job.status === 'Failed') {
                        statusClass = 'text-red-400';
                        statusIcon = '❌';
                    } else if (job.status === 'Running') {
                        statusClass = 'text-blue-400';
                        statusIcon = '🔄';
                    }

                    html += `<tr class="border-t border-gray-700 hover:bg-gray-750">
                        <td class="px-4 py-3 font-mono text-sm">${job.name}</td>
                        <td class="px-4 py-3 text-sm ${statusClass}">${statusIcon} ${job.status}</td>
                        <td class="px-4 py-3 text-sm text-gray-400">${started}</td>
                        <td class="px-4 py-3 text-sm space-x-2">
                            <button onclick="viewLogs('${job.name}')" class="text-blue-400 hover:text-blue-300">Logs</button>
                            <button onclick="deleteJob('${job.name}')" class="text-red-400 hover:text-red-300">Delete</button>
                        </td>
                    </tr>`;
                }

                html += '</tbody></table>';
                container.innerHTML = html;
            } catch (err) {
                container.innerHTML = `<div class="p-4 text-red-400">Error: ${err.message}</div>`;
            }
        }

        async function triggerJob(jobType) {
            if (!confirm(`Trigger ${jobType} job?`)) return;

            try {
                const res = await fetch('/api/trigger', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ job_type: jobType, namespace })
                });

                const data = await res.json();

                if (res.ok) {
                    alert(`Job created: ${data.job_name}`);
                    loadJobs();
                } else {
                    alert(`Error: ${data.detail}`);
                }
            } catch (err) {
                alert(`Error: ${err.message}`);
            }
        }

        async function viewLogs(jobName) {
            const modal = document.getElementById('logsModal');
            const title = document.getElementById('logsTitle');
            const content = document.getElementById('logsContent').querySelector('pre');

            title.textContent = `Logs: ${jobName}`;
            content.textContent = 'Loading...';
            modal.classList.remove('hidden');
            modal.classList.add('flex');

            try {
                const res = await fetch(`/api/job/${jobName}/logs?namespace=${namespace}`);
                const data = await res.json();
                content.textContent = data.logs || 'No logs available';
            } catch (err) {
                content.textContent = `Error: ${err.message}`;
            }
        }

        function closeLogsModal() {
            const modal = document.getElementById('logsModal');
            modal.classList.add('hidden');
            modal.classList.remove('flex');
        }

        async function deleteJob(jobName) {
            if (!confirm(`Delete job ${jobName}?`)) return;

            try {
                const res = await fetch(`/api/job/${jobName}?namespace=${namespace}`, {
                    method: 'DELETE'
                });

                if (res.ok) {
                    loadJobs();
                } else {
                    const data = await res.json();
                    alert(`Error: ${data.detail}`);
                }
            } catch (err) {
                alert(`Error: ${err.message}`);
            }
        }

        // Close modal on escape
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') closeLogsModal();
        });

        // Initial load
        loadCronJobs();
        loadJobs();

        // Auto-refresh every 30 seconds
        setInterval(() => {
            loadCronJobs();
            loadJobs();
        }, 30000);
    </script>
</body>
</html>
"""
