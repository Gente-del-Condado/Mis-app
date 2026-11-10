FROM docker.io/library/python:3.13-alpine
RUN apk add --no-cache age git openssh-client tini \
    && mkdir -p /app /data /addons
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
ENV PGM_DATA=/config/private-git-manager PGM_LEGACY_DATA=/data PGM_ADDONS=/addons PGM_CORE_CONFIG=/homeassistant PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
EXPOSE 8099
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8099/health', timeout=3)"
ENTRYPOINT ["/sbin/tini", "--"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8099", "--no-proxy-headers", "--no-access-log", "--log-level", "warning"]
