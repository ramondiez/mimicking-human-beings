"""
Client Lambda stack for MCP Cluster CDK project.
"""
import os
import aws_cdk as cdk
from aws_cdk import (
    aws_ec2 as ec2,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_logs as logs,
    aws_sqs as sqs,
    aws_kms as kms,
    Duration,
    RemovalPolicy,
)
from constructs import Construct
from typing import Dict, Any, List


class ClientStack(cdk.Stack):
    """Client Lambda stack for MCP Cluster."""

    def __init__(
        self,
        scope: Construct,
        id: str,
        vpc: ec2.IVpc,
        lambda_security_group: ec2.ISecurityGroup,
        lambda_config: Dict[str, Any],
        url_fetcher_stack,  # Accept the stack directly
        random_web_stack,   # Accept the stack directly
        encryption_key: cdk.aws_kms.IKey = None,  # Accept an existing KMS key
        **kwargs
    ) -> None:
        """
        Initialize the client Lambda stack.
        
        Args:
            scope: CDK construct scope
            id: CDK construct ID
            vpc: VPC for the Lambda function
            lambda_security_group: Security group for Lambda
            lambda_config: Lambda configuration
            url_fetcher_stack: URL fetcher service stack
            random_web_stack: Random web service stack
            **kwargs: Additional arguments to pass to the parent class
        """
        super().__init__(scope, id, **kwargs)

        # Extract Lambda configuration
        memory_size = lambda_config.get("memory_size", 256)
        timeout_seconds = lambda_config.get("timeout_seconds", 30)
        reserved_concurrent_executions = lambda_config.get("reserved_concurrent_executions")
        environment_variables = lambda_config.get("environment_variables", {})
        
        # Add service URLs to environment variables directly from the stacks
        environment_variables["URL_FETCHER_URL"] = url_fetcher_stack.service_url
        environment_variables["RANDOM_WEB_URL"] = random_web_stack.service_url
        
        # Create Dead Letter Queue (DLQ) for Lambda function
        dlq = sqs.Queue(
            self,
            "DeadLetterQueue",
            queue_name=f"{id}-dlq",
            retention_period=Duration.days(14),  # Keep failed messages for 14 days
            # Always use KMS encryption with the provided key
            encryption=sqs.QueueEncryption.KMS,
            encryption_master_key=encryption_key,
            visibility_timeout=Duration.seconds(timeout_seconds * 6),  # 6x the function timeout
        )
        
        # Create Lambda execution role
        lambda_role = iam.Role(
            self,
            "LambdaExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaVPCAccessExecutionRole"),
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"),
            ]
        )
        
        # Add Bedrock permissions to the Lambda role (for Nova Lite model)
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                    "bedrock:GetModelCustomizationJob",
                    "bedrock:GetFoundationModel",
                    "bedrock:ListFoundationModels",
                ],
                # Scope to specific resources or use a condition if possible
                resources=["*"],
                # Add a condition to restrict to specific models if needed
                conditions={
                    "StringEquals": {
                        "aws:RequestedRegion": self.region
                    }
                }
            )
        )
        
        # Add SQS permissions to the Lambda role for DLQ
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "sqs:SendMessage",
                ],
                resources=[dlq.queue_arn]
            )
        )
        
        # Add KMS permissions to the Lambda role
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "kms:Decrypt",
                    "kms:DescribeKey",
                    "kms:Encrypt",
                    "kms:ReEncrypt*",
                    "kms:GenerateDataKey*",
                ],
                resources=[encryption_key.key_arn]
            )
        )
        
        # Create Lambda layer for mcp_client
        mcp_client_layer = lambda_.LayerVersion(
            self,
            "MCPClientLayer",
            code=lambda_.Code.from_asset("../dist/mcp_client_layer.zip"),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_10],
            description="MCP Client Layer",
        )
        
        # Create Lambda function with DLQ configuration and environment variable encryption
        lambda_function_props = {
            "function_name": f"{id}-client",
            "runtime": lambda_.Runtime.PYTHON_3_10,
            "handler": "lambda_handler.handler",
            "code": lambda_.Code.from_asset("../cdk/lambda"),
            "role": lambda_role,
            "vpc": vpc,
            "vpc_subnets": ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            "security_groups": [lambda_security_group],
            "memory_size": memory_size,
            "timeout": Duration.seconds(timeout_seconds),
            "environment": environment_variables,
            "reserved_concurrent_executions": reserved_concurrent_executions,
            "log_retention": logs.RetentionDays.ONE_WEEK,
            "layers": [mcp_client_layer],
            "dead_letter_queue": dlq,
            "dead_letter_queue_enabled": True,
            "retry_attempts": 2,
        }
        
        # Always add environment_encryption since we now have a dedicated key stack
        lambda_function_props["environment_encryption"] = encryption_key
        
        self.lambda_function = lambda_.Function(
            self,
            "ClientFunction",
            **lambda_function_props
        )
        
        # Create CloudWatch alarm for DLQ messages
        dlq_alarm = cdk.aws_cloudwatch.Alarm(
            self,
            "DLQAlarm",
            metric=dlq.metric_approximate_number_of_messages_visible(),
            threshold=1,
            evaluation_periods=1,
            alarm_description="Alarm when messages are sent to the Dead Letter Queue",
            alarm_name=f"{id}-dlq-alarm",
        )
        
        # Outputs
        cdk.CfnOutput(
            self,
            "LambdaFunctionName",
            value=self.lambda_function.function_name,
            description="Lambda function name",
            export_name=f"{id}-function-name",
        )
        
        cdk.CfnOutput(
            self,
            "LambdaFunctionArn",
            value=self.lambda_function.function_arn,
            description="Lambda function ARN",
            export_name=f"{id}-function-arn",
        )
        
        cdk.CfnOutput(
            self,
            "DeadLetterQueueUrl",
            value=dlq.queue_url,
            description="Dead Letter Queue URL",
            export_name=f"{id}-dlq-url",
        )
