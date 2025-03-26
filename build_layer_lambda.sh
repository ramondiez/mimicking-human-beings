#!/bin/bash
# Script to create a Lambda layer with all dependencies using the AWS Lambda Python 3.10 image

# Set error handling
set -e

echo "Building Lambda layer using AWS Lambda Python 3.10 image..."

# Create a temporary directory for the Dockerfile
TEMP_DIR=$(mktemp -d)
DOCKERFILE="$TEMP_DIR/Dockerfile"

# Create a Dockerfile for building the layer
cat > "$DOCKERFILE" << 'EOF'
FROM public.ecr.aws/lambda/python:3.10

# Install zip utility
RUN yum install -y zip

# Set up the layer directory structure
RUN mkdir -p /opt/python

# Copy requirements file
COPY requirements.txt .

# Install dependencies directly to the /opt/python directory
# Use --platform to ensure we get x86_64 compatible packages
RUN pip3 install --no-cache-dir --platform manylinux2014_x86_64 --implementation cp --python-version 3.10 --only-binary=:all: --upgrade -r requirements.txt -t /opt/python

# Copy the mcp_client package
COPY mcp_client /opt/python/mcp_client

# Create the layer zip
RUN cd /opt && zip -r /layer.zip python
EOF

# Create requirements.txt with specific versions
cat > "$TEMP_DIR/requirements.txt" << 'EOF'
#boto3==1.28.38
mcp==1.5.0
httpx==0.27
anyio>=4.5.0
pydantic==2.7.2
pydantic-settings==2.5.2
httpx-sse==0.4.0
#uvicorn==0.23.2
#starlette==0.27.0
exceptiongroup==1.1.3
typing-extensions==4.7.1
EOF

# Copy the mcp_client package to the temp directory
cp -r mcp_client "$TEMP_DIR/"

# Build the Docker image
echo "Building Docker image..."
docker build -t mcp-lambda-layer-builder "$TEMP_DIR"

# Create a container from the image and copy the layer.zip file
echo "Extracting layer.zip from container..."
mkdir -p dist
CONTAINER_ID=$(docker create mcp-lambda-layer-builder)
docker cp "$CONTAINER_ID:/layer.zip" dist/mcp_client_layer.zip
docker rm "$CONTAINER_ID"

# Clean up
rm -rf "$TEMP_DIR"

echo "Lambda layer created at dist/mcp_client_layer.zip"
echo "Layer size: $(du -h dist/mcp_client_layer.zip | cut -f1)"
