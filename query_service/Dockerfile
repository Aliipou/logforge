FROM python:3.11.12-slim-bookworm
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN pip install --upgrade pip
COPY query_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY common/ common/
COPY query_service/ query_service/
EXPOSE 8002
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 CMD curl -f http://localhost:8002/health || exit 1
CMD ["uvicorn", "query_service.main:app", "--host", "0.0.0.0", "--port", "8002", "--workers", "4"]
