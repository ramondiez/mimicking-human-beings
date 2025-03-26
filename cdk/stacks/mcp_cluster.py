"""
CDK stack for MCP cluster.
"""
from aws_cdk import (
    Stack,
    CfnOutput,
    aws_ecs as ecs,
    aws_iam as iam,
    aws_kms as kms,
    RemovalPolicy,
)
from constructs import Construct

from ..constructs import DockerImageBuilder, MCPService, MCPNetwork
from ..config import Environment
from ..mcp_constructs.iam_policies import create_kms_key_policy


class MCPClusterStack(Stack):
    """
    CDK Stack for deploying MCP servers to ECS.
    """

    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        """
        Initialize the MCP cluster stack.
        
        Args:
            scope: CDK construct scope
            id: CDK construct ID
            **kwargs: Additional arguments to pass to the parent class
        """
        super().__init__(scope, id, **kwargs)

        # Create a single KMS key for the entire stack with proper policy
        encryption_key = kms.Key(
            self,
            "EncryptionKey",
            description="KMS key for encrypting MCP Cluster resources",
            enable_key_rotation=True,
            removal_policy=RemovalPolicy.RETAIN,  # Keep the key even if the stack is deleted
            alias=f"{id}-key",
            policy=create_kms_key_policy(self.account, self.region)
        )

        # Build and push Docker images
        image_builder = DockerImageBuilder()
        image_builder.login_to_ecr()
        
        # Get service configurations
        services = Environment.get_services()
        
        # Build and push Docker images
        image_uris = {}
        for service_name, service_config in services.items():
            image_uris[service_name] = image_builder.build_and_push(
                service_config.name,
                service_config.dockerfile
            )

        # Create network infrastructure
        network = MCPNetwork(
            self, 
            "Network", 
            encryption_key=encryption_key,
            account_id=self.account,
            region=self.region
        )

        # Create ECS Cluster
        cluster = ecs.Cluster(
            self, "Cluster",
            vpc=network.vpc,
            container_insights=True,
        )

        # Create ECS Task Execution Role with constrained permissions
        execution_role = iam.Role(
            self, "TaskExecutionRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
        )
        
        # Add required permissions with constraints
        execution_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ecr:GetAuthorizationToken",
                    "ecr:BatchCheckLayerAvailability",
                    "ecr:GetDownloadUrlForLayer",
                    "ecr:BatchGetImage"
                ],
                resources=["*"],  # ECR GetAuthorizationToken requires '*'
                conditions={
                    "StringEquals": {
                        "aws:SourceAccount": self.account
                    }
                }
            )
        )

        # Create services
        for service_name, service_config in services.items():
            MCPService(
                self, f"{service_name.capitalize()}Service",
                cluster=cluster,
                vpc=network.vpc,
                execution_role=execution_role,
                security_group=network.ecs_security_group,
                listener=network.listener,
                name=service_config.name,
                image_uri=image_uris[service_name],
                port=service_config.port,
                path_pattern=service_config.path_pattern,
                environment=service_config.environment,
                encryption_key=encryption_key,  # Pass the encryption key to the service
            )

        # Output the ALB DNS name
        CfnOutput(
            self, "LoadBalancerDNS",
            value=network.alb.load_balancer_dns_name,
            description="DNS name of the load balancer"
        )
        
        # Output the KMS key ARN
        CfnOutput(
            self, "EncryptionKeyArn",
            value=encryption_key.key_arn,
            description="ARN of the KMS encryption key"
        )
