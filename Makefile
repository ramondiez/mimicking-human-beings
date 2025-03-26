.PHONY: setup install dev clean format build build-client build-server docker-build docker-up docker-down cdk-bootstrap cdk-deploy cdk-synth

# Use uv for package management
UV := uv

setup:
	@echo "Installing uv if not already installed..."
	@pip install uv
	@echo "Setting up development environment..."
	@$(UV) venv
	@$(UV) pip install -e .

install:
	@echo "Installing dependencies with uv..."
	@$(UV) pip install -r requirements.txt

dev:
	@echo "Installing development dependencies with uv..."
	@$(UV) pip install -e ".[dev]"

clean:
	@echo "Cleaning up build artifacts..."
	@rm -rf build/
	@rm -rf dist/
	@rm -rf *.egg-info/
	@rm -rf .pytest_cache/
	@find . -type d -name __pycache__ -exec rm -rf {} +
	@find . -type f -name "*.pyc" -delete

format:
	@echo "Formatting code with black and isort..."
	@$(UV) pip run black mcp_server mcp_client examples cdk
	@$(UV) pip run isort mcp_server mcp_client examples cdk

build:
	@echo "Building wheel packages..."
	@$(UV) pip install build
	@$(UV) pip run build

build-client:
	@echo "Building mcp_client wheel..."
	@$(UV) pip install build
	@$(UV) pip run build --wheel --outdir dist/ --config-setting=packages=mcp_client

build-server:
	@echo "Building mcp_server wheel..."
	@$(UV) pip install build
	@$(UV) pip run build --wheel --outdir dist/ --config-setting=packages=mcp_server

docker-build:
	@echo "Building Docker images..."
	@docker-compose build --no-cache

docker-up:
	@echo "Starting Docker containers..."
	@docker-compose up -d

docker-down:
	@echo "Stopping Docker containers..."
	@docker-compose down

cdk-bootstrap:
	@echo "Bootstrapping CDK..."
	@cd cdk && pip install -r requirements.txt
	@cd cdk && cdk bootstrap

cdk-deploy:
	@echo "Deploying CDK stack..."
	@cd cdk && cdk deploy

cdk-synth:
	@echo "Synthesizing CDK stack..."
	@cd cdk && cdk synth

help:
	@echo "Available commands:"
	@echo "  setup        - Install uv and set up development environment"
	@echo "  install      - Install dependencies with uv"
	@echo "  dev          - Install development dependencies"
	@echo "  clean        - Remove build artifacts"
	@echo "  format       - Format code with black and isort"
	@echo "  build        - Build wheel packages for both client and server"
	@echo "  build-client - Build wheel package for client only"
	@echo "  build-server - Build wheel package for server only"
	@echo "  docker-build - Build Docker images"
	@echo "  docker-up    - Start Docker containers"
	@echo "  docker-down  - Stop Docker containers"
	@echo "  cdk-bootstrap - Bootstrap CDK environment"
	@echo "  cdk-deploy   - Deploy CDK stack"
	@echo "  cdk-synth    - Synthesize CDK stack"