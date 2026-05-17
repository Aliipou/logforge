FROM python:3.11.12-slim-bookworm
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN pip install --upgrade pip
COPY processor_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY common/ common/
COPY processor_service/ processor_service/
CMD ["python", "-m", "processor_service.main"]
