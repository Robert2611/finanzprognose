FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TZ=Europe/Berlin
RUN apt-get update && apt-get install -y --no-install-recommends tzdata && rm -rf /var/lib/apt/lists/*
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
# Deploy files (production compose file, install.sh, update.sh). install.sh/update.sh copy them
# out of the image, so a release always brings matching scripts along.
COPY deploy /deploy
# Release tag (e.g. v1.4.0), set by the release workflow. update.sh reads the label.
ARG APP_VERSION=dev
ENV APP_VERSION=$APP_VERSION
LABEL finanzprognose.version=$APP_VERSION
EXPOSE 8000
HEALTHCHECK --interval=60s --timeout=5s --start-period=30s --start-interval=2s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')"
# Deliberately only 1 worker: write access and the backup scheduler run in a single process.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
