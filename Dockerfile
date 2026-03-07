FROM python:3.12-slim
WORKDIR /app
COPY api/requirements.txt ./api/requirements.txt
RUN pip install --no-cache-dir -r api/requirements.txt
COPY api/        ./api/
COPY ingestion/  ./ingestion/
COPY scripts/    ./scripts/
COPY benchmarks/ ./benchmarks/
CMD ["sh", "-c", "cd /app/api && python /app/scripts/migrate.py && python /app/scripts/import_benchmarks.py /app/benchmarks && exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
