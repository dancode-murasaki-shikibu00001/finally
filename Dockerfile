# FinAlly — Multi-stage Dockerfile
# Stage 1: Build Next.js frontend static export
# Stage 2: Python/FastAPI runtime with static files served by FastAPI

# ─── Stage 1: Frontend Build ───────────────────────────────────────────────
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend

# Install dependencies first (layer caching)
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --prefer-offline || npm install

# Copy source and build static export
COPY frontend/ ./
RUN npm run build

# ─── Stage 2: Backend Runtime ──────────────────────────────────────────────
FROM python:3.12-slim AS runtime
WORKDIR /app

# Install uv (fast Python package manager)
RUN pip install uv --no-cache-dir

# Install Python dependencies (layer caching — copy lockfile before source)
COPY backend/pyproject.toml backend/uv.lock* ./backend/
WORKDIR /app/backend
RUN uv sync --no-dev --frozen 2>/dev/null || uv sync --no-dev

# Copy backend application source
COPY backend/ /app/backend/

# Copy Next.js static export from frontend builder stage
# FastAPI will serve these as static files on /*
COPY --from=frontend-builder /app/frontend/out /app/backend/static/

# Volume mount point for SQLite database persistence
# Map to /app/db at runtime: docker run -v finally-data:/app/db ...
VOLUME /app/db

EXPOSE 8000

WORKDIR /app/backend
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
