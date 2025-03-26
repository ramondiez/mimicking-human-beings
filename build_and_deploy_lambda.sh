#!/bin/bash
# Script to build the Lambda layer using the Lambda-compatible Docker image and deploy the CDK stack

# Set error handling
set -e

echo "Building mcp_client layer..."
./build_layer_lambda.sh

# Check if the layer was created
if [ -f "dist/mcp_client_layer.zip" ]; then
    echo "Layer built successfully: dist/mcp_client_layer.zip"
    
    # Deploy the CDK stack
    echo "Deploying CDK stack..."
    cd cdk && cdk deploy --all --require-approval never
else
    echo "Error: Layer build failed"
    exit 1
fi
