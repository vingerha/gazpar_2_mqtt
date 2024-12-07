FROM python:3.13-slim-bookworm

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    unzip \
    xvfb \
    libxi6 \
    libgconf-2-4 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Install bashio for Home Assistant integration
ARG BASHIO_VERSION="0.16.2"
RUN mkdir -p /tmp/bashio \
    && curl -f -L -s -S "https://github.com/hassio-addons/bashio/archive/v${BASHIO_VERSION}.tar.gz" | tar -xzf - --strip 1 -C /tmp/bashio \
    && mv /tmp/bashio/lib /usr/lib/bashio \
    && ln -s /usr/lib/bashio/bashio /usr/bin/bashio \
    && rm -rf /tmp/bashio

# Create app user early to minimize attack surface
RUN groupadd -r appuser && useradd -r -g appuser -s /bin/sh -M appuser \
    && mkdir -p /data /app \
    && chown -R appuser:appuser /app /data

# Set environment
ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    TZ=Europe/Paris \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1

# Copy requirements first for better caching
COPY --chown=appuser:appuser ./app/requirement.txt /app/
RUN pip3 install --no-cache-dir --upgrade pip && \
    pip3 install --no-cache-dir -r requirement.txt

# Copy application code
COPY --chown=appuser:appuser ./app /app/
COPY --chown=root:root entrypoint.sh /usr/local/bin/

# Set permissions
RUN chmod 755 /usr/local/bin/entrypoint.sh && \
    chmod 755 /app && \
    chmod 777 /data

VOLUME ["/data"]

HEALTHCHECK --interval=5m --timeout=3s \
  CMD ps aux | grep 'python3 /app/gazpar2mqtt.py' | grep -v grep || exit 1

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["python3", "/app/gazpar2mqtt.py"]