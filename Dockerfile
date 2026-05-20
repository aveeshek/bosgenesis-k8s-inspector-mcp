FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN useradd -u 10001 -m appuser

COPY pyproject.toml README.md /app/
COPY src /app/src
COPY config /app/config

RUN pip install --upgrade pip && pip install .

RUN mkdir -p /var/log/bosgenesis-k8s-inspector && \
    chown -R appuser:appuser /var/log/bosgenesis-k8s-inspector /app

USER 10001:10001

EXPOSE 8080

CMD ["python", "-m", "bosgenesis_k8s_inspector_mcp.main"]
