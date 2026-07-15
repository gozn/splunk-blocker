FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PROJECT_ROOT=/app \
    DB_PATH=/app/db/splunk_blocker.db \
    LOG_FILE_PATH=/var/log/splunk-blocker/splunk_alerts.log

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY config ./config
COPY public ./public
COPY run.py .

RUN mkdir -p /app/db /var/log/splunk-blocker

EXPOSE 6666

CMD ["gunicorn", "--bind", "0.0.0.0:6666", "--workers", "2", "--access-logfile", "-", "--error-logfile", "-", "run:app"]
