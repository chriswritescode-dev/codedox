# Unified Docker container for CodeDox (API + Frontend)
FROM node:18-alpine AS frontend_builder

WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci --legacy-peer-deps
COPY frontend/ ./
RUN npm run build


FROM python:3.10-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy Python requirements
COPY requirements.txt .

# Install Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Copy Python source
COPY src/ ./src/
COPY migrations/ ./migrations/
COPY migrate.py cli.py ./

# Copy built frontend
COPY --from=frontend_builder /app/frontend/dist /app/static

# Create logs directory
RUN mkdir -p logs

# Environment
ENV PYTHONPATH=/app
ENV DB_HOST=localhost
ENV DB_PORT=5432
ENV API_HOST=0.0.0.0
ENV API_PORT=8002

# Run migrations on container creation, then start API which serves static files
CMD python migrate.py 2>/dev/null || true && python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8002
