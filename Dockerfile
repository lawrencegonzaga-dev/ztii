FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8501 \
    ZTII_API_PORT=8000 \
    ZTII_API_URL=http://127.0.0.1:8000 \
    ZTII_DATABASE_PATH=/tmp/ztii/ztii.db \
    ZTII_ENABLE_SYNC_WORKER=false

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    useradd --create-home --uid 10001 ztii && \
    mkdir -p /tmp/ztii && chown -R ztii:ztii /tmp/ztii

COPY --chown=ztii:ztii . .

USER ztii
EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=3)"

CMD ["python", "start.py"]
