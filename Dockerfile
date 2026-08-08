FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY vector_drift_watch/ vector_drift_watch/

ENTRYPOINT ["python", "-m", "vector_drift_watch.cli"]
CMD ["--help"]
