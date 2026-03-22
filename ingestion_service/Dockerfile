FROM python:3.11-slim AS base
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

FROM base AS builder
RUN pip install --upgrade pip
COPY ingestion_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM base AS production
RUN groupadd --gid 1001 appgroup && useradd --uid 1001 --gid appgroup --no-create-home appuser
COPY --from=builder /usr/local/lib/python3.11 /usr/local/lib/python3.11
COPY --from=builder /usr/local/bin /usr/local/bin
COPY common/ common/
COPY ingestion_service/ ingestion_service/
USER appuser
EXPOSE 8001
CMD ["uvicorn", "ingestion_service.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "2"]
