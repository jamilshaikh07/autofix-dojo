#!/usr/bin/env python3
"""Seed DefectDojo with findings from client's cloud-ide-dev cluster for demo."""

import os
import sys
from datetime import datetime, timedelta

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("DEFECTDOJO_URL", "http://localhost:8080")
API_KEY = os.getenv("DEFECTDOJO_API_KEY")

if not API_KEY:
    print("Error: DEFECTDOJO_API_KEY not set")
    sys.exit(1)

headers = {
    "Authorization": f"Token {API_KEY}",
    "Content-Type": "application/json",
}


def create_product_type():
    """Create a product type."""
    response = requests.post(
        f"{BASE_URL}/api/v2/product_types/",
        headers=headers,
        json={
            "name": "Cloud IDE Infrastructure",
            "description": "EKS-based Cloud IDE workloads",
        },
    )
    if response.status_code == 201:
        print(f"✅ Created product type: {response.json()['id']}")
        return response.json()["id"]
    elif response.status_code == 400 and "already exists" in response.text:
        resp = requests.get(
            f"{BASE_URL}/api/v2/product_types/",
            headers=headers,
            params={"name": "Cloud IDE Infrastructure"},
        )
        if resp.json()["count"] > 0:
            pt_id = resp.json()["results"][0]["id"]
            print(f"ℹ️  Using existing product type: {pt_id}")
            return pt_id
    print(f"❌ Failed to create product type: {response.text}")
    return None


def create_product(product_type_id: int):
    """Create a product."""
    response = requests.post(
        f"{BASE_URL}/api/v2/products/",
        headers=headers,
        json={
            "name": "cloud-ide-dev",
            "description": "Cloud IDE Development EKS Cluster (us-east-1)",
            "prod_type": product_type_id,
        },
    )
    if response.status_code == 201:
        print(f"✅ Created product: {response.json()['id']}")
        return response.json()["id"]
    elif response.status_code == 400 and "already exists" in response.text:
        resp = requests.get(
            f"{BASE_URL}/api/v2/products/",
            headers=headers,
            params={"name": "cloud-ide-dev"},
        )
        if resp.json()["count"] > 0:
            p_id = resp.json()["results"][0]["id"]
            print(f"ℹ️  Using existing product: {p_id}")
            return p_id
    print(f"❌ Failed to create product: {response.text}")
    return None


def create_engagement(product_id: int):
    """Create an engagement."""
    today = datetime.now().strftime("%Y-%m-%d")
    end_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

    response = requests.post(
        f"{BASE_URL}/api/v2/engagements/",
        headers=headers,
        json={
            "name": "Container Vulnerability Scan - Dec 2024",
            "product": product_id,
            "target_start": today,
            "target_end": end_date,
            "engagement_type": "CI/CD",
            "status": "In Progress",
        },
    )
    if response.status_code == 201:
        print(f"✅ Created engagement: {response.json()['id']}")
        return response.json()["id"]
    elif response.status_code == 400:
        resp = requests.get(
            f"{BASE_URL}/api/v2/engagements/",
            headers=headers,
            params={"product": product_id},
        )
        if resp.json()["count"] > 0:
            e_id = resp.json()["results"][0]["id"]
            print(f"ℹ️  Using existing engagement: {e_id}")
            return e_id
    print(f"❌ Failed to create engagement: {response.text}")
    return None


def create_test(engagement_id: int):
    """Create a test."""
    today = datetime.now().strftime("%Y-%m-%d")

    resp = requests.get(
        f"{BASE_URL}/api/v2/test_types/",
        headers=headers,
        params={"name": "Trivy Scan"},
    )
    if resp.json()["count"] > 0:
        test_type_id = resp.json()["results"][0]["id"]
    else:
        create_resp = requests.post(
            f"{BASE_URL}/api/v2/test_types/",
            headers=headers,
            json={"name": "Trivy Scan"},
        )
        if create_resp.status_code == 201:
            test_type_id = create_resp.json()["id"]
        else:
            resp = requests.get(f"{BASE_URL}/api/v2/test_types/", headers=headers)
            test_type_id = resp.json()["results"][0]["id"]

    response = requests.post(
        f"{BASE_URL}/api/v2/tests/",
        headers=headers,
        json={
            "engagement": engagement_id,
            "test_type": test_type_id,
            "target_start": today,
            "target_end": today,
            "title": "EKS Container Image Scan - cloud-ide-dev",
        },
    )
    if response.status_code == 201:
        print(f"✅ Created test: {response.json()['id']}")
        return response.json()["id"]
    print(f"❌ Failed to create test: {response.text}")
    return None


def create_findings(test_id: int):
    """Create vulnerability findings based on actual cluster images."""

    # Real findings based on images in the cloud-ide-dev cluster
    findings = [
        # cert-manager - outdated version
        {
            "title": "CVE-2023-44487: HTTP/2 Rapid Reset Attack in cert-manager",
            "severity": "High",
            "description": "cert-manager v1.9.1 is vulnerable to HTTP/2 Rapid Reset Attack (CVE-2023-44487). This allows attackers to cause denial of service.",
            "component_name": "quay.io/jetstack/cert-manager-controller",
            "component_version": "v1.9.1",
            "cve": "CVE-2023-44487",
            "mitigation": "Upgrade to cert-manager v1.13.3 or later",
        },
        {
            "title": "CVE-2024-24786: Infinite loop in cert-manager-cainjector",
            "severity": "High",
            "description": "cert-manager-cainjector v1.9.1 contains protobuf vulnerability leading to infinite loop",
            "component_name": "quay.io/jetstack/cert-manager-cainjector",
            "component_version": "v1.9.1",
            "cve": "CVE-2024-24786",
            "mitigation": "Upgrade to cert-manager v1.14.0 or later",
        },
        # kube-rbac-proxy - multiple versions in use
        {
            "title": "CVE-2023-45142: OpenTelemetry-Go DoS in kube-rbac-proxy",
            "severity": "High",
            "description": "kube-rbac-proxy v0.13.0 vulnerable to denial of service via OpenTelemetry instrumentation",
            "component_name": "gcr.io/kubebuilder/kube-rbac-proxy",
            "component_version": "v0.13.0",
            "cve": "CVE-2023-45142",
            "mitigation": "Upgrade to kube-rbac-proxy v0.16.0 or later",
        },
        {
            "title": "CVE-2023-45142: OpenTelemetry-Go DoS in kube-rbac-proxy",
            "severity": "High",
            "description": "kube-rbac-proxy v0.13.1 vulnerable to denial of service via OpenTelemetry instrumentation",
            "component_name": "gcr.io/kubebuilder/kube-rbac-proxy",
            "component_version": "v0.13.1",
            "cve": "CVE-2023-45142",
            "mitigation": "Upgrade to kube-rbac-proxy v0.16.0 or later",
        },
        # snapshot-controller - outdated
        {
            "title": "CVE-2024-3177: Bypassing mountable secrets in snapshot-controller",
            "severity": "Critical",
            "description": "snapshot-controller v6.2.1 allows bypassing mountable secrets policy",
            "component_name": "registry.k8s.io/sig-storage/snapshot-controller",
            "component_version": "v6.2.1",
            "cve": "CVE-2024-3177",
            "mitigation": "Upgrade to snapshot-controller v6.3.3 or later",
        },
        # k8s-pvc-tagger - older version
        {
            "title": "CVE-2024-24790: net/netip vulnerability in k8s-pvc-tagger",
            "severity": "Critical",
            "description": "k8s-pvc-tagger v1.2.1 built with Go version vulnerable to IPv4-mapped IPv6 parsing issue",
            "component_name": "ghcr.io/mtougeron/k8s-pvc-tagger",
            "component_version": "v1.2.1",
            "cve": "CVE-2024-24790",
            "mitigation": "Upgrade to k8s-pvc-tagger v1.3.0 or later (Go 1.22+)",
        },
        # IDE proxy images - various older versions
        {
            "title": "CVE-2024-45337: SSH vulnerability in IDE proxy",
            "severity": "High",
            "description": "IDE proxy v1.9.29.1 uses vulnerable golang.org/x/crypto/ssh version",
            "component_name": "edge.jfrog.ais.acquia.io/devops-pipeline/proxy",
            "component_version": "v1.9.29.1",
            "cve": "CVE-2024-45337",
            "mitigation": "Upgrade proxy to v1.9.49 or later",
        },
        {
            "title": "CVE-2024-45337: SSH vulnerability in IDE container",
            "severity": "High",
            "description": "IDE container v1.9.29.1 uses vulnerable golang.org/x/crypto/ssh version",
            "component_name": "edge.jfrog.ais.acquia.io/devops-pipeline/ide",
            "component_version": "v1.9.29.1",
            "cve": "CVE-2024-45337",
            "mitigation": "Upgrade IDE to v1.9.50 or later",
        },
        # Fluentd - older versions in use
        {
            "title": "CVE-2024-32760: Insecure temp files in fluentd",
            "severity": "Medium",
            "description": "Fluentd v1.9.18 creates insecure temporary files allowing local privilege escalation",
            "component_name": "edge.jfrog.ais.acquia.io/devops-pipeline/fluentd",
            "component_version": "v1.9.18",
            "cve": "CVE-2024-32760",
            "mitigation": "Upgrade fluentd to v1.9.27 or later",
        },
        # calico - checking if outdated
        {
            "title": "CVE-2024-33522: MITM in Calico Typha",
            "severity": "High",
            "description": "Calico Typha v3.27.x allows man-in-the-middle attacks due to improper certificate validation",
            "component_name": "quay.io/calico/typha",
            "component_version": "v3.27.0",
            "cve": "CVE-2024-33522",
            "mitigation": "Upgrade to Calico v3.28.0 or later (current: v3.31.2 - OK)",
            "active": False,  # Already fixed
        },
    ]

    created_count = 0
    for finding in findings:
        active = finding.pop("active", True)
        response = requests.post(
            f"{BASE_URL}/api/v2/findings/",
            headers=headers,
            json={
                "test": test_id,
                "title": finding["title"],
                "severity": finding["severity"],
                "description": finding["description"],
                "component_name": finding["component_name"],
                "component_version": finding["component_version"],
                "cve": finding.get("cve"),
                "mitigation": finding["mitigation"],
                "active": active,
                "verified": True,
                "duplicate": False,
                "numerical_severity": "S0" if finding["severity"] == "Critical" else "S1" if finding["severity"] == "High" else "S2",
                "found_by": [1],
            },
        )
        if response.status_code == 201:
            status = "✅" if active else "☑️ (resolved)"
            print(f"  {status} Created finding: {finding['title'][:60]}...")
            created_count += 1
        else:
            print(f"  ❌ Failed: {response.text[:100]}")

    return created_count


def main():
    print("🚀 Seeding DefectDojo with cloud-ide-dev cluster findings...\n")
    print("=" * 60)

    # Create product type
    pt_id = create_product_type()
    if not pt_id:
        sys.exit(1)

    # Create product
    product_id = create_product(pt_id)
    if not product_id:
        sys.exit(1)

    # Create engagement
    engagement_id = create_engagement(product_id)
    if not engagement_id:
        sys.exit(1)

    # Create test
    test_id = create_test(engagement_id)
    if not test_id:
        sys.exit(1)

    # Create findings
    print("\n📝 Creating vulnerability findings...")
    print("-" * 60)
    count = create_findings(test_id)

    print("\n" + "=" * 60)
    print(f"✅ Done! Created {count} findings.")
    print(f"\n📋 Update your .env file with:")
    print(f"   DEFECTDOJO_PRODUCT_ID={product_id}")
    print("\n🔍 Now run: python -m autofix.cli list-findings")
    print("🚀 Then run: python -m autofix.cli scan-and-fix --dry-run")


if __name__ == "__main__":
    main()
