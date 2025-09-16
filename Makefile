# Makefile for joplin-mcp Docker development and deployment
NAME=joplin-mcp
TAG=$(shell git log -1 --pretty=%h)
DEV_PORT=8080
PROD_PORT=8081

# Default target
.PHONY: help
help:
	@echo "Joplin MCP Docker Commands:"
	@echo ""
	@echo "BUILD COMMANDS:"
	@echo "  make build-dev     - Build development image with hot-reload"
	@echo "  make build-prod    - Build production image"
	@echo "  make build-all     - Build both development and production"
	@echo ""
	@echo "RUN COMMANDS:"
	@echo "  make dev           - Run development container with volume mounting"
	@echo "  make prod          - Run production container"
	@echo "  make stop          - Stop running containers"
	@echo ""
	@echo "UTILITY COMMANDS:"
	@echo "  make install       - Install dependencies locally"
	@echo "  make test-local    - Test server locally (no Docker)"
	@echo "  make clean         - Remove Docker images and containers"
	@echo ""
	@echo "ENVIRONMENT:"
	@echo "  Set JOPLIN_TOKEN=your_webclipper_token before running"
	@echo "  Get token from: Joplin Desktop → Tools → Options → Web Clipper"

# Build targets
.PHONY: build-dev
build-dev:
	@echo "Building development image: ${NAME}:dev-${TAG}"
	docker build --target development -t ${NAME}:dev-${TAG} .
	docker tag ${NAME}:dev-${TAG} ${NAME}:dev-latest

.PHONY: build-prod
build-prod:
	@echo "Building production image: ${NAME}:prod-${TAG}"
	docker build --target production -t ${NAME}:prod-${TAG} .
	docker tag ${NAME}:prod-${TAG} ${NAME}:prod-latest

.PHONY: build-all
build-all: build-dev build-prod

# Run targets
.PHONY: dev
dev:
	@echo "Running development container on port ${DEV_PORT}"
	@echo "Source code will be mounted for hot-reload"
	@if [ -z "$$JOPLIN_TOKEN" ]; then echo "Error: JOPLIN_TOKEN not set"; exit 1; fi
	docker run --rm --name ${NAME}-dev \
		--network host \
		-v "$(shell pwd)/src:/app/src" \
		-e JOPLIN_TOKEN=$$JOPLIN_TOKEN \
		-e MCP_PORT=${DEV_PORT} \
		-p ${DEV_PORT}:${DEV_PORT} \
		${NAME}:dev-latest

.PHONY: prod
prod:
	@echo "Running production container on port ${PROD_PORT}"
	@if [ -z "$$JOPLIN_TOKEN" ]; then echo "Error: JOPLIN_TOKEN not set"; exit 1; fi
	docker run --rm --name ${NAME}-prod \
		--network host \
		-e JOPLIN_TOKEN=$$JOPLIN_TOKEN \
		-e MCP_PORT=${PROD_PORT} \
		-p ${PROD_PORT}:${PROD_PORT} \
		${NAME}:prod-latest

# Development helpers
.PHONY: dev-bg
dev-bg:
	@echo "Running development container in background"
	@if [ -z "$$JOPLIN_TOKEN" ]; then echo "Error: JOPLIN_TOKEN not set"; exit 1; fi
	docker run -d --name ${NAME}-dev \
		--network host \
		-v "$(shell pwd)/src:/app/src" \
		-e JOPLIN_TOKEN=$$JOPLIN_TOKEN \
		-e MCP_PORT=${DEV_PORT} \
		-p ${DEV_PORT}:${DEV_PORT} \
		${NAME}:dev-latest

.PHONY: logs
logs:
	docker logs -f ${NAME}-dev 2>/dev/null || docker logs -f ${NAME}-prod

.PHONY: shell
shell:
	docker exec -it ${NAME}-dev /bin/bash 2>/dev/null || docker exec -it ${NAME}-prod /bin/bash

# Stop containers
.PHONY: stop
stop:
	@echo "Stopping joplin-mcp containers"
	-docker stop ${NAME}-dev ${NAME}-prod 2>/dev/null
	-docker rm ${NAME}-dev ${NAME}-prod 2>/dev/null

# Local development (no Docker)
.PHONY: install
install:
	python -m pip install -e .

.PHONY: test-local
test-local:
	@echo "Testing server locally (ensure JOPLIN_TOKEN is set)"
	@if [ -z "$$JOPLIN_TOKEN" ]; then echo "Error: JOPLIN_TOKEN not set"; exit 1; fi
	python run_fastmcp_server.py

# Cleanup
.PHONY: clean
clean:
	@echo "Cleaning up Docker images and containers"
	-docker rm ${NAME}-dev ${NAME}-prod 2>/dev/null
	-docker rmi ${NAME}:dev-latest ${NAME}:prod-latest 2>/dev/null
	-docker rmi $(shell docker images ${NAME} -q) 2>/dev/null