# Multi-stage Dockerfile for joplin-mcp with development optimization
#
# BUILD COMMANDS:
# Production (self-contained, recommended for most users):
#   docker build --target production -t joplin-mcp:prod .
#
# Development (with volume mounting for hot-reload):
#   docker build --target development -t joplin-mcp:dev .
#
# RUN COMMANDS:
# Production (get JOPLIN_TOKEN from Joplin Desktop → Tools → Options → Web Clipper):
#   docker run --network host -p 8080:8080 -e JOPLIN_TOKEN=your_webclipper_token joplin-mcp:prod
#
# Development (mount source code for live editing):
#   docker run --network host -v $(pwd)/src:/app/src -p 8080:8080 -e JOPLIN_TOKEN=your_webclipper_token joplin-mcp:dev
#
# Multi-MCP Setup (use different ports for each MCP):
#   docker run --network host -p 8081:8081 -e JOPLIN_TOKEN=token -e MCP_PORT=8081 joplin-mcp:prod
#   docker run --network host -p 8082:8082 -e OTHER_MCP_TOKEN=token -e MCP_PORT=8082 other-mcp:prod
#
# NOTE: Get your JOPLIN_TOKEN from:
#   Joplin Desktop → Tools → Options → Web Clipper → Authorization token
# NOTE: --network host is required to access Joplin web clipper at localhost:41184

FROM python:3.13-slim AS base

WORKDIR /app

# Copy dependency files and install dependencies only (not the project itself yet)
# This layer is cached and reused unless pyproject.toml changes
COPY pyproject.toml ./
RUN python -m pip install --no-cache-dir build && \
    python -m pip install --no-cache-dir $(python -c "import tomllib; f=open('pyproject.toml','rb'); data=tomllib.load(f); f.close(); print(' '.join(data['project']['dependencies']))")

# Set common environment
ENV PYTHONPATH=/app

# Default MCP port (configurable via MCP_PORT env var)
ENV MCP_PORT=8080

# Production stage - optimized for deployment (recommended for most users)
FROM base AS production

# Copy source code into image (no volume mounting)
COPY src/ ./src/
COPY run_fastmcp_server.py ./

# Final install of the project itself
RUN python -m pip install --no-cache-dir .

# Set production environment
ENV JOPLIN_MCP_ENV=production

# Expose configurable MCP port
EXPOSE ${MCP_PORT}

# Production entry point with configurable transport
# Supports STDIO (default), HTTP, SSE transports
CMD ["python", "run_fastmcp_server.py"]

# Development stage - optimized for rapid iteration
FROM base AS development

# Install dev dependencies for debugging/testing
RUN python -c "import tomllib; f=open('pyproject.toml','rb'); data=tomllib.load(f); f.close(); dev_deps=data.get('project',{}).get('optional-dependencies',{}).get('dev',[]); import subprocess; subprocess.run(['python','-m','pip','install','--no-cache-dir']+dev_deps) if dev_deps else None"

# Copy the server entry point
COPY run_fastmcp_server.py ./

# Create volume mount points for hot-reload
# Source code will be mounted from host at runtime
VOLUME ["/app/src"]

# Set development environment
ENV JOPLIN_MCP_ENV=development
ENV PYTHONUNBUFFERED=1

# Enable FastMCP auto-reload if supported
ENV FASTMCP_AUTO_RELOAD=true

# Expose configurable MCP port
EXPOSE ${MCP_PORT}

# Development entry point with auto-reload
# Note: src/ directory will be volume mounted at runtime
CMD ["python", "run_fastmcp_server.py"]