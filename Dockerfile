# Small official Python image.
FROM python:3.12-slim

# No .pyc files; log output appears immediately; Python finds our package in src/.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app

# Install libraries first: this layer is cached until requirements.txt changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Then copy the code (changes often, so it comes last).
COPY src/ ./src/

# Run as a normal user, not root. It needs a writable folder for log files.
RUN useradd --create-home appuser \
    && mkdir -p /app/logs \
    && chown appuser /app/logs
USER appuser

# Default command: run the pipeline once.
CMD ["python", "-m", "fx_pipeline.main"]