"""
Key management stack for MCP Cluster CDK project.
"""
import aws_cdk as cdk
from aws_cdk import (
    aws_kms as kms,
    RemovalPolicy,
)
from constructs import Construct


class KeyStack(cdk.Stack):
    """Key management stack for MCP Cluster."""

    def __init__(
        self,
        scope: Construct,
        id: str,
        **kwargs
    ) -> None:
        """
        Initialize the key management stack.
        
        Args:
            scope: CDK construct scope
            id: CDK construct ID
            **kwargs: Additional arguments to pass to the parent class
        """
        super().__init__(scope, id, **kwargs)

        # Create a single KMS key for the entire project
        self.encryption_key = kms.Key(
            self,
            "EncryptionKey",
            description=f"KMS key for encrypting {id} resources",
            enable_key_rotation=True,
            removal_policy=RemovalPolicy.RETAIN,  # Keep the key even if the stack is deleted
            alias=f"alias/{id.lower()}-key"
        )
        
        # Add a policy statement to allow Lambda service to use the key
        self.encryption_key.add_to_resource_policy(
            cdk.aws_iam.PolicyStatement(
                actions=[
                    "kms:Decrypt",
                    "kms:DescribeKey",
                    "kms:Encrypt",
                    "kms:ReEncrypt*",
                    "kms:GenerateDataKey*",
                ],
                resources=["*"],
                principals=[cdk.aws_iam.ServicePrincipal("lambda.amazonaws.com")],
                conditions={
                    "StringEquals": {
                        "aws:SourceAccount": cdk.Aws.ACCOUNT_ID
                    }
                }
            )
        )
        
        # Add a policy statement to allow ECS service to use the key
        self.encryption_key.add_to_resource_policy(
            cdk.aws_iam.PolicyStatement(
                actions=[
                    "kms:Decrypt",
                    "kms:DescribeKey",
                    "kms:Encrypt",
                    "kms:ReEncrypt*",
                    "kms:GenerateDataKey*",
                ],
                resources=["*"],
                principals=[cdk.aws_iam.ServicePrincipal("ecs.amazonaws.com")],
                conditions={
                    "StringEquals": {
                        "aws:SourceAccount": cdk.Aws.ACCOUNT_ID
                    }
                }
            )
        )
        
        # Add a policy statement to allow CloudWatch Logs to use the key
        self.encryption_key.add_to_resource_policy(
            cdk.aws_iam.PolicyStatement(
                actions=[
                    "kms:Decrypt",
                    "kms:DescribeKey",
                    "kms:Encrypt",
                    "kms:ReEncrypt*",
                    "kms:GenerateDataKey*",
                ],
                resources=["*"],
                principals=[cdk.aws_iam.ServicePrincipal("logs.amazonaws.com")],
                conditions={
                    "StringEquals": {
                        "aws:SourceAccount": cdk.Aws.ACCOUNT_ID
                    }
                }
            )
        )
        
        # Outputs
        cdk.CfnOutput(
            self,
            "EncryptionKeyArn",
            value=self.encryption_key.key_arn,
            description="KMS encryption key ARN",
            export_name=f"{id}-encryption-key-arn",
        )
        
        cdk.CfnOutput(
            self,
            "EncryptionKeyId",
            value=self.encryption_key.key_id,
            description="KMS encryption key ID",
            export_name=f"{id}-encryption-key-id",
        )
