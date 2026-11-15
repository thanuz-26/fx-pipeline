.PHONY: up run test down

# Start the database in the background.
up:
	docker compose up -d postgres

# Rebuild the pipeline image (picks up code changes), then run the pipeline once.
run:
	docker compose build pipeline
	docker compose run --rm pipeline

# Run the tests (activate .venv first).
test:
	pytest

# Stop and remove the containers. Data in the volume is kept.
down:
	docker compose down