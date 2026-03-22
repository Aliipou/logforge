# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2024-01-15

### Added
- Ingestion service: FastAPI + Kafka producer with Redis rate limiting (sliding window)
- Processor service: Kafka consumer with batch inserts (100 records / 500ms), retry logic, Dead Letter Queue
- Query service: filtering, full-text search (PostgreSQL GIN), time-range queries, Redis caching, error rate aggregations
- PostgreSQL schema with UUID primary keys, JSONB metadata, GIN indexes for FTS
- Docker Compose stack: Kafka + Zookeeper + PostgreSQL + Redis + all services
- GitHub Actions CI: lint (ruff + mypy), unit tests, docker build check
- Rate limiting: 100 req/min per IP using Redis sorted sets
- Graceful shutdown: flushes Kafka batch on SIGTERM
