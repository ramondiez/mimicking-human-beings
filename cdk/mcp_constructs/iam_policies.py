"""
IAM policies for MCP Cluster with proper constraints.
"""
from aws_cdk import (
    aws_iam as iam,
    aws_s3 as s3,
    Stack,
)

def create_ecs_task_role(scope: Stack, id: str, service_name: str) -> iam.Role:
    """
    Create an ECS task role with properly constrained permissions.
    """
    task_role = iam.Role(
        scope,
        f"{id}TaskRole",
        assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
    )

    # Add CloudWatch Logs permissions with constraints
    task_role.add_to_policy(
        iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            resources=[
                f"arn:aws:logs:{Stack.of(scope).region}:{Stack.of(scope).account}:log-group:/ecs/{service_name}:*",
                f"arn:aws:logs:{Stack.of(scope).region}:{Stack.of(scope).account}:log-group:/ecs/{service_name}:log-stream:*"
            ],
            conditions={
                "StringEquals": {
                    "aws:SourceAccount": Stack.of(scope).account
                }
            }
        )
    )

    return task_role

def create_ecs_execution_role(scope: Stack, id: str, service_name: str, kms_key_arn: str) -> iam.Role:
    """
    Create an ECS execution role with properly constrained permissions.
    """
    execution_role = iam.Role(
        scope,
        f"{id}ExecutionRole",
        assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
    )

    # Add ECR permissions - this is required for pulling images
    execution_role.add_to_policy(
        iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "ecr:GetAuthorizationToken",  # Required for docker pull
                "ecr:BatchCheckLayerAvailability",
                "ecr:GetDownloadUrlForLayer",
                "ecr:BatchGetImage"
            ],
            resources=["*"],  # GetAuthorizationToken requires '*' as resource
        )
    )

    # Add CloudWatch Logs permissions with constraints
    execution_role.add_to_policy(
        iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            resources=[
                f"arn:aws:logs:{Stack.of(scope).region}:{Stack.of(scope).account}:log-group:/ecs/{service_name}:*"
            ],
            conditions={
                "StringEquals": {
                    "aws:SourceAccount": Stack.of(scope).account
                }
            }
        )
    )

    # Add KMS permissions with constraints
    if kms_key_arn:
        execution_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "kms:Decrypt",
                    "kms:GenerateDataKey"
                ],
                resources=[kms_key_arn],
                conditions={
                    "StringEquals": {
                        "aws:SourceAccount": Stack.of(scope).account
                    }
                }
            )
        )

    return execution_role

def create_alb_s3_access_policy(bucket: s3.IBucket, account_id: str, region: str) -> iam.PolicyStatement:
    """
    Create a policy statement for ALB to write access logs to S3.
    """
    return iam.PolicyStatement(
        effect=iam.Effect.ALLOW,
        principals=[iam.ServicePrincipal("delivery.logs.amazonaws.com")],
        actions=["s3:PutObject"],
        resources=[bucket.arn_for_objects("AWSLogs/" + account_id + "/*")],
        conditions={
            "StringEquals": {
                "s3:x-amz-acl": "bucket-owner-full-control",
                "aws:SourceAccount": account_id
            },
            "StringLike": {
                "aws:SourceArn": f"arn:aws:elasticloadbalancing:{region}:{account_id}:*"
            }
        }
    )

def create_kms_key_policy(account_id: str, region: str) -> iam.PolicyDocument:
    """
    Create a KMS key policy with proper constraints.
    """
    return iam.PolicyDocument(
        statements=[
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                principals=[iam.AccountRootPrincipal()],
                actions=["kms:*"],
                resources=["*"],
                conditions={
                    "StringEquals": {
                        "aws:SourceAccount": account_id
                    }
                }
            ),
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                principals=[
                    iam.ServicePrincipal("logs.amazonaws.com"),
                    iam.ServicePrincipal("delivery.logs.amazonaws.com")
                ],
                actions=[
                    "kms:Decrypt",
                    "kms:GenerateDataKey"
                ],
                resources=["*"],
                conditions={
                    "StringEquals": {
                        "aws:SourceAccount": account_id
                    },
                    "ArnLike": {
                        "aws:SourceArn": [
                            f"arn:aws:logs:{region}:{account_id}:*",
                            f"arn:aws:elasticloadbalancing:{region}:{account_id}:*"
                        ]
                    }
                }
            )
        ]
    )
