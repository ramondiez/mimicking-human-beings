"""
Network stack for MCP Cluster CDK project.
"""
import aws_cdk as cdk
from aws_cdk import aws_ec2 as ec2
from constructs import Construct
from typing import Dict, Any


class NetworkStack(cdk.Stack):
    """Network stack for MCP Cluster."""

    def __init__(
        self,
        scope: Construct,
        id: str,
        vpc_config: Dict[str, Any],
        **kwargs
    ) -> None:
        """
        Initialize the network stack.
        
        Args:
            scope: CDK construct scope
            id: CDK construct ID
            vpc_config: VPC configuration
            **kwargs: Additional arguments to pass to the parent class
        """
        super().__init__(scope, id, **kwargs)

        # Extract VPC configuration
        cidr = vpc_config.get("cidr", "10.0.0.0/16")
        max_azs = vpc_config.get("max_azs", 2)
        nat_gateways = vpc_config.get("nat_gateways", 1)
        subnet_config = vpc_config.get("subnet_configuration", {})
        
        # Create VPC with public and private subnets
        self.vpc = ec2.Vpc(
            self,
            "VPC",
            vpc_name=f"{id}-vpc",
            ip_addresses=ec2.IpAddresses.cidr(cidr),
            max_azs=max_azs,
            nat_gateways=nat_gateways,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=subnet_config.get("public_subnet_cidr_mask", 24),
                ),
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=subnet_config.get("private_subnet_cidr_mask", 24),
                ),
                ec2.SubnetConfiguration(
                    name="Isolated",
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                    cidr_mask=subnet_config.get("isolated_subnet_cidr_mask", 28),
                ),
            ],
        )
        
        # Create security groups for different components
        
        # ALB security group - allows inbound HTTP/HTTPS only from within the VPC
        self.alb_security_group = ec2.SecurityGroup(
            self,
            "ALBSecurityGroup",
            vpc=self.vpc,
            description="Security group for Application Load Balancers",
            allow_all_outbound=True,
        )
        # Only allow HTTP traffic from specific sources, not 0.0.0.0/0
        # For production, you should restrict this to your organization's IP ranges
        # or use a WAF to protect your ALB
        self.alb_security_group.add_ingress_rule(
            ec2.Peer.ipv4(self.vpc.vpc_cidr_block),
            ec2.Port.tcp(80),
            "Allow HTTP traffic only from within the VPC"
        )
        self.alb_security_group.add_ingress_rule(
            ec2.Peer.ipv4(self.vpc.vpc_cidr_block),
            ec2.Port.tcp(443),
            "Allow HTTPS traffic only from within the VPC"
        )
        
        # ECS security group - allows inbound traffic from ALB
        self.ecs_security_group = ec2.SecurityGroup(
            self,
            "ECSSecurityGroup",
            vpc=self.vpc,
            description="Security group for ECS services",
            allow_all_outbound=True,
        )
        self.ecs_security_group.add_ingress_rule(
            self.alb_security_group,
            ec2.Port.tcp_range(8000, 9000),
            "Allow traffic from ALB on ports 8000-9000"
        )
        
        # Lambda security group - allows outbound traffic only
        self.lambda_security_group = ec2.SecurityGroup(
            self,
            "LambdaSecurityGroup",
            vpc=self.vpc,
            description="Security group for Lambda functions",
            allow_all_outbound=True,
        )
        
        # Create VPC endpoints for AWS services
        
        # S3 Gateway Endpoint
        self.s3_endpoint = ec2.GatewayVpcEndpoint(
            self,
            "S3Endpoint",
            vpc=self.vpc,
            service=ec2.GatewayVpcEndpointAwsService.S3,
        )
        
        # DynamoDB Gateway Endpoint
        self.dynamodb_endpoint = ec2.GatewayVpcEndpoint(
            self,
            "DynamoDBEndpoint",
            vpc=self.vpc,
            service=ec2.GatewayVpcEndpointAwsService.DYNAMODB,
        )
        
        # ECR Interface Endpoints
        self.ecr_api_endpoint = ec2.InterfaceVpcEndpoint(
            self,
            "ECRApiEndpoint",
            vpc=self.vpc,
            service=ec2.InterfaceVpcEndpointAwsService.ECR,
            private_dns_enabled=True,
            subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            security_groups=[self.ecs_security_group],
        )
        
        self.ecr_dkr_endpoint = ec2.InterfaceVpcEndpoint(
            self,
            "ECRDkrEndpoint",
            vpc=self.vpc,
            service=ec2.InterfaceVpcEndpointAwsService.ECR_DOCKER,
            private_dns_enabled=True,
            subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            security_groups=[self.ecs_security_group],
        )
        
        # CloudWatch Logs Interface Endpoint
        self.logs_endpoint = ec2.InterfaceVpcEndpoint(
            self,
            "LogsEndpoint",
            vpc=self.vpc,
            service=ec2.InterfaceVpcEndpointAwsService.CLOUDWATCH_LOGS,
            private_dns_enabled=True,
            subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            security_groups=[self.ecs_security_group, self.lambda_security_group],
        )
        
        # Outputs
        cdk.CfnOutput(
            self,
            "VpcId",
            value=self.vpc.vpc_id,
            description="VPC ID",
            export_name=f"{id}-vpc-id",
        )
        
        cdk.CfnOutput(
            self,
            "PrivateSubnets",
            value=",".join([subnet.subnet_id for subnet in self.vpc.private_subnets]),
            description="Private subnet IDs",
            export_name=f"{id}-private-subnet-ids",
        )
        
        cdk.CfnOutput(
            self,
            "PublicSubnets",
            value=",".join([subnet.subnet_id for subnet in self.vpc.public_subnets]),
            description="Public subnet IDs",
            export_name=f"{id}-public-subnet-ids",
        )
        
        cdk.CfnOutput(
            self,
            "IsolatedSubnets",
            value=",".join([subnet.subnet_id for subnet in self.vpc.isolated_subnets]),
            description="Isolated subnet IDs",
            export_name=f"{id}-isolated-subnet-ids",
        )
        
        cdk.CfnOutput(
            self,
            "EcsSecurityGroupId",
            value=self.ecs_security_group.security_group_id,
            description="ECS security group ID",
            export_name=f"{id}-ecs-sg-id",
        )
        
        cdk.CfnOutput(
            self,
            "AlbSecurityGroupId",
            value=self.alb_security_group.security_group_id,
            description="ALB security group ID",
            export_name=f"{id}-alb-sg-id",
        )
        
        cdk.CfnOutput(
            self,
            "LambdaSecurityGroupId",
            value=self.lambda_security_group.security_group_id,
            description="Lambda security group ID",
            export_name=f"{id}-lambda-sg-id",
        )
