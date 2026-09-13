FROM python:3.10-slim AS builder

WORKDIR /build

RUN pip install --no-cache-dir uv

COPY pyproject.toml ./
COPY app ./app

# CPU app API sets INSTALL_ML=true (guest selfie). Celery CPU workers leave it false.
ARG INSTALL_ML=false
RUN if [ "$INSTALL_ML" = "true" ]; then \
      uv pip install --system --no-cache ".[ml]"; \
    else \
      uv pip install --system --no-cache .; \
    fi

FROM python:3.10-slim AS runtime

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 appuser

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --chmod=755 docker-entrypoint.sh ./docker-entrypoint.sh
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app

RUN mkdir -p /app/models && chown appuser:appuser /app/models

USER appuser

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV ML_DEVICE=cpu

EXPOSE 8000

ENTRYPOINT ["./docker-entrypoint.sh"]

# Default API command. Production backend with ML uses --workers 1 (see compose).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
