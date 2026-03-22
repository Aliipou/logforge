# Contributing to LogForge

## Setup

```bash
git clone https://github.com/Aliipou/logforge
cd logforge
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
```

## Running the Stack

```bash
docker compose up -d        # Start all services
make ingest-sample          # Send a test log
make query-errors           # Query ERROR logs
```

## Running Tests

```bash
make test       # Full suite
make lint       # ruff + mypy
```

Coverage must not decrease. All new code needs tests.

## Pull Request Guidelines

- Title must follow Conventional Commits: `feat:`, `fix:`, `docs:`, `perf:`, `test:`, `chore:`
- One logical change per PR
- Update CHANGELOG.md under `[Unreleased]`
- CI must pass before review

## Architecture Constraints

**Never write to PostgreSQL from the ingestion service.** Kafka is the durability layer.
All writes go through the processor service.

## Reporting Bugs

Open an issue with the `bug` template. Include: steps to reproduce, expected vs actual behavior, service logs (`docker compose logs <service>`).
