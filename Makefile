.PHONY: up down logs test lint build

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

build:
	docker compose build

test:
	pytest tests/ -v

lint:
	ruff check . --fix
	mypy ingestion_service processor_service query_service common

ingest-sample:
	curl -s -X POST http://localhost:8001/logs \
		-H "Content-Type: application/json" \
		-d '{"service_name":"auth-service","level":"ERROR","message":"JWT validation failed","metadata":{"user_id":42}}'

query-errors:
	curl -s "http://localhost:8002/logs?level=ERROR&page_size=5" | python -m json.tool
