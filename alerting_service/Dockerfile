FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN pip install asyncpg pydantic-settings
COPY common/ common/
COPY alerting_service/ alerting_service/
CMD ["python", "-m", "alerting_service.main"]
