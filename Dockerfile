# Unified Docker container for CodeDox (API + Frontend)
FROM node:18-alpine AS frontend_builder

WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci --legacy-peer-deps
COPY frontend/ ./
RUN npm run build


FROM python:3.10-slim

# Install runtime dependencies and Playwright system requirements
RUN apt-get update && apt-get install -y \
    libpq5 \
    # Playwright browser dependencies
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libatspi2.0-0 \
    libwayland-client0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy Python requirements
COPY requirements.txt .

# Install Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install --with-deps chromium

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
CMD python migrate.py || echo "WARNING: Migration failed but continuing..."; python -m uvicorn src.api.main:app --host $API_HOST --port $API_PORT
