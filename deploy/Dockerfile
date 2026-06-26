# syntax=docker/dockerfile:1
# Slim, single-purpose image. Target < 500MB; no GPU, no large weights, no
# runtime downloads. Binds 0.0.0.0:$PORT and serves /health within seconds.
FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOST=0.0.0.0 \
    PORT=8000

WORKDIR /app

# libgomp1 is required by scipy/scikit-learn (OpenMP runtime).
RUN apt-get update \
 && apt-get install -y --no-install-recommends libgomp1 \
 && rm -rf /var/lib/apt/lists/*

# 1) Dependencies first (cached layer).
COPY requirements.txt ./
RUN pip install -r requirements.txt

# 2) Source + packaging metadata.
COPY pyproject.toml README.md ./
COPY src ./src
COPY scripts ./scripts
COPY deploy ./deploy

# 3) Train the tiny fallback model so it matches the installed sklearn, then
#    install the package (artifact ships as package-data).
RUN python scripts/train_classifier.py \
 && pip install --no-deps .

# Run as a non-root user.
RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health').status==200 else 1)"

CMD ["gunicorn", "-c", "deploy/gunicorn_conf.py", "queuestorm.main:app"]
