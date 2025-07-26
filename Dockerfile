# Build stage
FROM python:3.10-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    python3-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Runtime stage
FROM python:3.10-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    gnupg

# Install runtime dependencies and Playwright requirements
RUN apt-get update && apt-get install -y \
    libpq5 \
    wget \
\
    # Dependencies for Chromium/Playwright
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libatspi2.0-0 \
    libx11-6 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libxcb1 \
    libxkbcommon0 \
    libgtk-3-0 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 codedox

# Set working directory
WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY --chown=codedox:codedox . .

# Create necessary directories
RUN mkdir -p logs && chown codedox:codedox logs

# Copy and set up entrypoint script
COPY --chown=root:root docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Install Node.js and npm for frontend dependencies (including Prettier)
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# Install frontend dependencies (including Prettier for code formatting)
WORKDIR /app/frontend
COPY --chown=codedox:codedox frontend/package*.json ./
RUN npm install && \
    chown -R codedox:codedox node_modules

WORKDIR /app

# Install Playwright browsers as root with proper setup
USER root
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright-browsers
RUN mkdir -p ${PLAYWRIGHT_BROWSERS_PATH} && \
    python -m playwright install chromium --with-deps && \
    chmod -R 755 ${PLAYWRIGHT_BROWSERS_PATH}

# Set environment for codedox user to find browsers
USER codedox
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright-browsers

# Set Python path
ENV PYTHONPATH=/app

# Set entrypoint
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

# Default command (can be overridden)
CMD ["python", "-m", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]