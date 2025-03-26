"""
ECS Cluster stack for MCP Cluster CDK project.
"""
import aws_cdk as cdk
from aws_cdk import (
    aws_ec2 as ec2,
    aws_ecs as ecs,
)
from constructs import Construct


class ClusterStack(cdk.Stack):
    """ECS Cluster stack for MCP Cluster."""

    def __init__(
        self,
        scope: Construct,
        id: str,
        vpc: ec2.IVpc,
        **kwargs
    ) -> None:
        """
        Initialize the ECS Cluster stack.
        
        Args:
            scope: CDK construct scope
            id: CDK construct ID
            vpc: VPC for the cluster
            **kwargs: Additional arguments to pass to the parent class
        """
        super().__init__(scope, id, **kwargs)

        # Create ECS cluster
        self.cluster = ecs.Cluster(
            self,
            "Cluster",
            vpc=vpc,
            container_insights=True,
            cluster_name=f"{id}-cluster",
        )
        
        # Outputs
        cdk.CfnOutput(
            self,
            "ClusterName",
            value=self.cluster.cluster_name,
            description="ECS Cluster name",
            export_name=f"{id}-cluster-name",
        )
        
        cdk.CfnOutput(
            self,
            "ClusterArn",
            value=self.cluster.cluster_arn,
            description="ECS Cluster ARN",
            export_name=f"{id}-cluster-arn",
        )
