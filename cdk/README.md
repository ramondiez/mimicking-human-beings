# Modular MCP Cluster CDK

This directory contains a modular AWS CDK implementation for deploying the MCP cluster to AWS.

## Project Structure

```
cdk/
├── app.py                  # Main CDK app entry point
├── cdk.json                # CDK configuration
├── requirements.txt        # CDK dependencies
├── config/                 # Configuration
│   ├── __init__.py
│   ├── environment.py      # Service configuration
│   ├── settings.yaml       # Environment settings
│   └── config_loader.py    # Configuration loader
├── constructs/             # Reusable constructs
│   ├── __init__.py
│   ├── docker_builder.py   # Docker image builder
├── stacks/                 # Stack definitions
│   ├── __init__.py
│   ├── network_stack.py    # Network infrastructure stack
│   ├── service_stack.py    # Service stack for MCP services
│   └── client_stack.py     # Client Lambda stack
└── lambda/                 # Lambda function code
    ├── lambda_handler.py   # Lambda handler
    ├── requirements.txt    # Lambda dependencies
    └── Dockerfile          # Lambda container image
```

## Architecture

The modular CDK project deploys the following components:

1. **Network Stack**:
   - VPC with public, private, and isolated subnets
   - NAT Gateways for outbound connectivity
   - Security groups for each component
   - VPC endpoints for AWS services

2. **Service Stacks**:
   - One stack per MCP server (URL fetcher and Random Web)
   - Each with its own Application Load Balancer
   - ECS Fargate tasks in private subnets

3. **Client Stack**:
   - Lambda function for the MCP client
   - VPC integration for private subnet deployment
   - IAM roles and permissions

## Deployment

```bash
# Install dependencies
pip install -r requirements.txt

# Deploy to development environment
cdk deploy --all --context environment=dev
```

## Configuration

Environment-specific configuration is stored in `config/settings.yaml`. Service configurations are in `config/environment.py`.

## Adding a New Service

To add a new service:

1. Add the service configuration to `config/environment.py`
2. Create a Dockerfile in the `docker/` directory
3. Deploy the stack with `cdk deploy --all`

## Useful Commands

* `cdk ls`          list all stacks in the app
* `cdk synth`       emits the synthesized CloudFormation template
* `cdk deploy`      deploy this stack to your default AWS account/region
* `cdk diff`        compare deployed stack with current state
* `cdk docs`        open CDK documentation
