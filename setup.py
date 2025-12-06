"""Setup script for autofix-dojo."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [
        line.strip()
        for line in fh
        if line.strip() and not line.startswith("#")
    ]

setup(
    name="autofix-dojo",
    version="0.2.0",
    author="Jamil Shaikh",
    author_email="jamil@example.com",
    description="Autonomous Vulnerability Remediation & Helm Chart Upgrade Operator",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/jamilshaikh07/autofix-dojo",
    packages=find_packages(exclude=["tests", "tests.*"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Security",
        "Topic :: System :: Systems Administration",
    ],
    python_requires=">=3.11",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "autofix-dojo=autofix.cli:main",
        ],
    },
    include_package_data=True,
)
