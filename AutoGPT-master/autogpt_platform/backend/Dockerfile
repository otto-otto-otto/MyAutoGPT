# ============================ DEPENDENCY BUILDER ============================ #

FROM debian:13-slim AS builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Use Aliyun mirror for Debian packages (required in China)
# Match both http:// and https:// in DEB822 format sources
RUN sed -i 's|https\?://deb.debian.org/debian|http://mirrors.aliyun.com/debian|g' /etc/apt/sources.list.d/debian.sources && \
    sed -i 's|https\?://security.debian.org/debian-security|http://mirrors.aliyun.com/debian-security|g' /etc/apt/sources.list.d/debian.sources

RUN echo 'Acquire::http::Pipeline-Depth 0;\nAcquire::http::No-Cache true;\nAcquire::BrokenProxy true;\n' > /etc/apt/apt.conf.d/99fixbadproxy

# Install Node.js via npmmirror binary (NodeSource is unreachable from China)
RUN apt-get update --allow-releaseinfo-change --fix-missing \
    && apt-get install -y curl ca-certificates gnupg xz-utils \
    && NODE_VERSION=20.19.0 \
    && ARCH=$(dpkg --print-architecture) \
    && case "$ARCH" in \
         amd64) NODE_ARCH="x64" ;; \
         arm64) NODE_ARCH="arm64" ;; \
         *) echo "Unsupported architecture: $ARCH" && exit 1 ;; \
       esac \
    && curl -fsSL https://npmmirror.com/mirrors/node/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-${NODE_ARCH}.tar.xz \
       -o /tmp/node.tar.xz \
    && tar -xJf /tmp/node.tar.xz -C /usr/local --strip-components=1 \
    && rm -f /tmp/node.tar.xz \
    && node --version && npm --version

# Update package list and install Python and build dependencies
# (Node.js is installed above via npmmirror binary)
RUN apt-get update \
    && apt-get install -y \
    python3.13 \
    python3.13-dev \
    python3.13-venv \
    python3-pip \
    build-essential \
    libpq5 \
    libz-dev \
    libssl-dev \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

ENV POETRY_HOME=/opt/poetry
ENV POETRY_NO_INTERACTION=1
ENV POETRY_VIRTUALENVS_CREATE=true
ENV POETRY_VIRTUALENVS_IN_PROJECT=true
ENV PATH=/opt/poetry/bin:$PATH

# Use Aliyun PyPI mirror for pip and Poetry (required in China)
RUN pip3 config set global.index-url https://mirrors.aliyun.com/pypi/simple/ && \
    pip3 config set global.trusted-host mirrors.aliyun.com

RUN pip3 install poetry --break-system-packages

# Copy and install dependencies
COPY autogpt_platform/autogpt_libs /app/autogpt_platform/autogpt_libs
COPY autogpt_platform/backend/poetry.lock autogpt_platform/backend/pyproject.toml /app/autogpt_platform/backend/
WORKDIR /app/autogpt_platform/backend

# Configure Poetry sources after pyproject.toml is in place
# In Poetry 2.x, "pypi" is a reserved name and can't be re-added.
# Strategy: remove default PyPI, use Tsinghua as primary (no pypi.org fallback — unreachable from China)
RUN poetry source remove pypi 2>/dev/null || true && \
    poetry source add --priority=primary tsinghua https://pypi.tuna.tsinghua.edu.cn/simple && \
    poetry lock

RUN poetry install --no-ansi --no-root

# Generate Prisma client
COPY autogpt_platform/backend/schema.prisma ./
COPY autogpt_platform/backend/backend/data/partial_types.py ./backend/data/partial_types.py
COPY autogpt_platform/backend/scripts/gen_prisma_types_stub.py ./scripts/
# Use npmmirror for Prisma engine binaries (required in China — GitHub Releases unreachable)
ENV PRISMA_ENGINES_MIRROR=https://registry.npmmirror.com/-/binary/prisma
RUN poetry run prisma generate && poetry run gen-prisma-stub

# ============================= MODEL TRAINER ============================== #

# Train security sandbox ML models during build.
# Uses the builder's .venv (which has scikit-learn, jieba, joblib).
# Outputs .pkl model files for the server stage to copy.
FROM builder AS model-trainer

WORKDIR /app/autogpt_platform/backend

# Copy training code and datasets
COPY autogpt_platform/backend/backend/security_sandbox/ ./backend/security_sandbox/

# Train models — outputs to backend/security_sandbox/models/
RUN poetry run python -m backend.security_sandbox.training.train_all

# =============================== DB MIGRATOR =============================== #

# Lightweight migrate stage - only needs Prisma CLI, not full Python environment
FROM debian:13-slim AS migrate

WORKDIR /app/autogpt_platform/backend

ENV DEBIAN_FRONTEND=noninteractive

# Use Aliyun mirror for Debian packages
# Match both http:// and https:// in DEB822 format sources
RUN sed -i 's|https\?://deb.debian.org/debian|http://mirrors.aliyun.com/debian|g' /etc/apt/sources.list.d/debian.sources && \
    sed -i 's|https\?://security.debian.org/debian-security|http://mirrors.aliyun.com/debian-security|g' /etc/apt/sources.list.d/debian.sources

# Install only what's needed for prisma migrate: Node.js and minimal Python for prisma-python
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.13 \
    python3-pip \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy Node.js from builder (needed for Prisma CLI)
# Node.js was installed to /usr/local via npmmirror binary
COPY --from=builder /usr/local/bin/node /usr/local/bin/node
COPY --from=builder /usr/local/lib/node_modules /usr/local/lib/node_modules
COPY --from=builder /usr/local/bin/npm /usr/local/bin/npm
COPY --from=builder /usr/local/bin/npx /usr/local/bin/npx

# Copy Prisma binaries
COPY --from=builder /root/.cache/prisma-python/binaries /root/.cache/prisma-python/binaries

# Use Aliyun PyPI mirror for pip (required in China)
RUN pip3 config set global.index-url https://mirrors.aliyun.com/pypi/simple/ && \
    pip3 config set global.trusted-host mirrors.aliyun.com

# Install prisma-client-py directly (much smaller than copying full venv)
# Use npmmirror for Prisma engine binaries (required in China)
ENV PRISMA_ENGINES_MIRROR=https://registry.npmmirror.com/-/binary/prisma
RUN pip3 install prisma>=0.15.0 --break-system-packages

COPY autogpt_platform/backend/schema.prisma ./
COPY autogpt_platform/backend/backend/data/partial_types.py ./backend/data/partial_types.py
COPY autogpt_platform/backend/scripts/gen_prisma_types_stub.py ./scripts/
COPY autogpt_platform/backend/migrations ./migrations

# ============================== BACKEND SERVER ============================== #

FROM debian:13-slim AS server

WORKDIR /app

ENV DEBIAN_FRONTEND=noninteractive

# Use Aliyun mirror for Debian packages (required in China)
# Match both http:// and https:// in DEB822 format sources
RUN sed -i 's|https\?://deb.debian.org/debian|http://mirrors.aliyun.com/debian|g' /etc/apt/sources.list.d/debian.sources && \
    sed -i 's|https\?://security.debian.org/debian-security|http://mirrors.aliyun.com/debian-security|g' /etc/apt/sources.list.d/debian.sources

# Install Python, FFmpeg, ImageMagick, and CLI tools for agent use.
# bubblewrap provides OS-level sandbox (whitelist-only FS + no network)
# for the bash_exec MCP tool (fallback when E2B is not configured).
# Using --no-install-recommends saves ~650MB by skipping unnecessary deps like llvm, mesa, etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.13 \
    python3-pip \
    ffmpeg \
    imagemagick \
    jq \
    ripgrep \
    tree \
    bubblewrap \
    && rm -rf /var/lib/apt/lists/*

# Copy poetry (build-time only, for `poetry install --only-root` to create entry points)
COPY --from=builder /usr/local/lib/python3* /usr/local/lib/python3*
COPY --from=builder /usr/local/bin/poetry /usr/local/bin/poetry
# Copy Node.js installation for Prisma and agent-browser.
# Node.js was installed to /usr/local via npmmirror binary.
# npm/npx are in /usr/local/bin alongside node; symlink for compatibility.
COPY --from=builder /usr/local/bin/node /usr/local/bin/node
COPY --from=builder /usr/local/lib/node_modules /usr/local/lib/node_modules
COPY --from=builder /usr/local/bin/npm /usr/local/bin/npm
COPY --from=builder /usr/local/bin/npx /usr/local/bin/npx
RUN ln -sf /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -sf /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx
COPY --from=builder /root/.cache/prisma-python/binaries /root/.cache/prisma-python/binaries

# Install agent-browser (Copilot browser tool) using the system chromium package.
# Chrome for Testing (the binary agent-browser downloads via `agent-browser install`)
# has no ARM64 builds, so we use the distro-packaged chromium instead — verified to
# work with agent-browser via Docker tests on arm64; amd64 is validated in CI.
# Note: system chromium tracks the Debian package schedule rather than a pinned
# Chrome for Testing release. If agent-browser requires a specific Chrome version,
# verify compatibility against the chromium package version in the base image.
# Skip bundled browser downloads — we use the system chromium package instead.
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=1
RUN apt-get update \
    && apt-get install -y --no-install-recommends chromium fonts-liberation \
    && rm -rf /var/lib/apt/lists/* \
    && npm config set registry https://registry.npmmirror.com \
    && npm install -g agent-browser \
    && rm -rf /tmp/* /root/.npm

ENV AGENT_BROWSER_EXECUTABLE_PATH=/usr/bin/chromium

WORKDIR /app/autogpt_platform/backend

# Copy only the .venv from builder (not the entire /app directory)
# The .venv includes the generated Prisma client
COPY --from=builder /app/autogpt_platform/backend/.venv ./.venv
ENV PATH="/app/autogpt_platform/backend/.venv/bin:$PATH"

# Copy dependency files + autogpt_libs (path dependency)
COPY autogpt_platform/autogpt_libs /app/autogpt_platform/autogpt_libs
# Copy builder's pyproject.toml + lock file — both are already resolved together
# in the builder stage, so we can skip the expensive re-lock below.
COPY --from=builder /app/autogpt_platform/backend/pyproject.toml ./
COPY --from=builder /app/autogpt_platform/backend/poetry.lock ./

# Copy backend code + docs (for Copilot docs search)
COPY autogpt_platform/backend ./
# Restore builder's pyproject.toml + poetry.lock (overwritten by the backend
# copy above).  Keeping both from the builder ensures they stay in sync with
# the builder's .venv — no re-lock needed.
COPY --from=builder /app/autogpt_platform/backend/pyproject.toml ./
COPY --from=builder /app/autogpt_platform/backend/poetry.lock ./
COPY docs /app/docs
# Copy pre-trained security sandbox ML models from model-trainer stage
COPY --from=model-trainer /app/autogpt_platform/backend/backend/security_sandbox/models/*.pkl ./backend/security_sandbox/models/
COPY --from=model-trainer /app/autogpt_platform/backend/backend/security_sandbox/models/*.json ./backend/security_sandbox/models/
# Install the project package to create entry point scripts in .venv/bin/
# (e.g., rest, executor, ws, db, scheduler, notification — see [tool.poetry.scripts])
# Uses the builder's pyproject.toml + lock (already consistent — no re-lock).
RUN poetry source remove pypi 2>/dev/null || true && \
    poetry source add --priority=primary tsinghua https://pypi.tuna.tsinghua.edu.cn/simple && \
    poetry install --no-ansi --only-root

ENV PORT=8000

CMD ["rest"]
