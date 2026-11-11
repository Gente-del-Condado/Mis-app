FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIVIGIA_DATA=/data PIVIGIA_MODELS=/opt/pivigia/models
WORKDIR /opt/pivigia
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY scripts/download_model.py ./scripts/download_model.py
COPY src/pivigia/i18n.py ./src/pivigia/i18n.py
COPY src/pivigia/locales ./src/pivigia/locales
RUN python scripts/download_model.py
COPY pyproject.toml LICENSE ./
COPY src ./src
COPY run.py ./run.py
RUN pip install --no-cache-dir --no-deps .
ARG BUILD_ARCH=aarch64
ARG BUILD_VERSION=0.1.6
LABEL io.hass.type="app" io.hass.version="${BUILD_VERSION}" io.hass.arch="${BUILD_ARCH}"
EXPOSE 2525 8099
CMD ["python", "run.py"]
