# autofix-dojo Dockerfile
# Multi-stage build for minimal production image

# Build stage
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Copy application code and metadata
COPY autofix/ ./autofix/
COPY pyproject.toml setup.py README.md ./

# Install the package
RUN pip install --no-cache-dir --user .

# Production stage
FROM python:3.11-slim

LABEL org.opencontainers.image.title="autofix-dojo"
LABEL org.opencontainers.image.description="Autonomous Vulnerability Remediation & Helm Chart Upgrade Operator"
LABEL org.opencontainers.image.source="https://github.com/jamilshaikh07/autofix-dojo"
LABEL org.opencontainers.image.version="0.2.0"

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install kubectl
RUN curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" \
    && chmod +x kubectl \
    && mv kubectl /usr/local/bin/

# Install Helm
RUN curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Install GitHub CLI
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
    && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
    && apt-get update \
    && apt-get install -y gh \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -g 1000 autofix && \
    useradd -u 1000 -g autofix -m -s /bin/bash autofix

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /root/.local /home/autofix/.local

# Copy application code
COPY --chown=autofix:autofix autofix/ ./autofix/

# Set environment
ENV PATH=/home/autofix/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Switch to non-root user
USER autofix

# Create data directory
RUN mkdir -p /home/autofix/data

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import autofix; print('healthy')" || exit 1

# Default command
ENTRYPOINT ["python", "-m", "autofix.cli"]
CMD ["--help"]
