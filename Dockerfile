# ==============================================================================
# PauliBot Django Application Dockerfile
# ==============================================================================
# Author: Senior Full-Stack Developer & DevOps Engineer
# Purpose: Build containerized Django application for production deployment
#
# Build Instructions:
#   docker build -t paulibot:latest .
#
# This Dockerfile packages the application; release validation is still required.
# - Python 3.11 (optimized for Django 4.x+)
# - PostgreSQL client libraries
# - Gunicorn WSGI server
# - All Python dependencies from requirements.txt
# ==============================================================================

FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install system dependencies
# - postgresql-client: Required for psycopg2
# - gcc: Required for compiling Python packages
RUN apt-get update && apt-get install -y \
    postgresql-client \
    gcc \
    python3-dev \
    musl-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch==2.10.0 --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . /app/

# Create directory for static files
RUN mkdir -p /app/staticfiles

# Expose port 8000
EXPOSE 8000

# Run migrations and start server (overridden by docker-compose)
CMD ["gunicorn", "paulibot.wsgi:application", "--config", "python:paulibot.gunicorn_conf", "--bind", "0.0.0.0:8000"]
