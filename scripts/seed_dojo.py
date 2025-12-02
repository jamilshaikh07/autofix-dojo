#!/usr/bin/env python3
"""Seed DefectDojo with test data for the autofix-dojo MVP."""

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
            "name": "Kubernetes Workloads",
            "description": "Container-based workloads running in Kubernetes",
        },
    )
    if response.status_code == 201:
        print(f"✅ Created product type: {response.json()['id']}")
        return response.json()["id"]
    elif response.status_code == 400 and "already exists" in response.text:
        # Get existing
        resp = requests.get(
            f"{BASE_URL}/api/v2/product_types/",
            headers=headers,
            params={"name": "Kubernetes Workloads"},
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
            "name": "Homelab GitOps",
            "description": "Kubernetes manifests for homelab cluster",
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
            params={"name": "Homelab GitOps"},
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
            "name": "Container Security Scan",
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
        # Try to get existing
        resp = requests.get(
            f"{BASE_URL}/api/v2/engagements/",
            headers=headers,
            params={"product": product_id, "name": "Container Security Scan"},
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

    # Get test type for "Container Scan"
    resp = requests.get(
        f"{BASE_URL}/api/v2/test_types/",
        headers=headers,
        params={"name": "Trivy Scan"},
    )
    if resp.json()["count"] > 0:
        test_type_id = resp.json()["results"][0]["id"]
    else:
        # Create test type
        create_resp = requests.post(
            f"{BASE_URL}/api/v2/test_types/",
            headers=headers,
            json={"name": "Trivy Scan"},
        )
        if create_resp.status_code == 201:
            test_type_id = create_resp.json()["id"]
        else:
            # Use a generic one
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
            "title": "Automated Container Scan",
        },
    )
    if response.status_code == 201:
        print(f"✅ Created test: {response.json()['id']}")
        return response.json()["id"]
    print(f"❌ Failed to create test: {response.text}")
    return None


def create_findings(test_id: int):
    """Create sample vulnerability findings."""
    findings = [
        {
            "title": "CVE-2024-1234: Buffer overflow in traefik/whoami",
            "severity": "Critical",
            "description": "A critical buffer overflow vulnerability was found in traefik/whoami:latest",
            "component_name": "traefik/whoami",
            "component_version": "latest",
            "cve": "CVE-2024-1234",
            "mitigation": "Upgrade to traefik/whoami:v1.10.3 or later",
        },
        {
            "title": "CVE-2024-5678: nginx security vulnerability",
            "severity": "High",
            "description": "High severity vulnerability in nginx:1.23.1",
            "component_name": "nginx",
            "component_version": "1.23.1",
            "cve": "CVE-2024-5678",
            "mitigation": "Upgrade to nginx:1.23.4 or later",
        },
        {
            "title": "CVE-2024-9012: Redis memory corruption",
            "severity": "High",
            "description": "Memory corruption vulnerability in redis:7.0.0",
            "component_name": "redis",
            "component_version": "7.0.0",
            "cve": "CVE-2024-9012",
            "mitigation": "Upgrade to redis:7.0.14 or later",
        },
        {
            "title": "CVE-2024-3456: Python dependency vulnerability",
            "severity": "Critical",
            "description": "Critical vulnerability in python:3.11.0 base image",
            "component_name": "python",
            "component_version": "3.11.0",
            "cve": "CVE-2024-3456",
            "mitigation": "Upgrade to python:3.11.7 or later",
        },
    ]

    created_count = 0
    for finding in findings:
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
                "active": True,
                "verified": True,
                "duplicate": False,
                "numerical_severity": "S0" if finding["severity"] == "Critical" else "S1",
                "found_by": [1],  # Scanner tool ID
            },
        )
        if response.status_code == 201:
            print(f"  ✅ Created finding: {finding['title'][:50]}...")
            created_count += 1
        else:
            print(f"  ❌ Failed: {response.text[:100]}")

    return created_count


def main():
    print("🚀 Seeding DefectDojo with test data...\n")

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
    print("\n📝 Creating findings...")
    count = create_findings(test_id)

    print(f"\n✅ Done! Created {count} findings.")
    print(f"\n📋 Update your .env file with:")
    print(f"   DEFECTDOJO_PRODUCT_ID={product_id}")


if __name__ == "__main__":
    main()
