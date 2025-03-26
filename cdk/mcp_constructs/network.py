"""
Network infrastructure constructs for MCP cluster.
"""
from constructs import Construct
from aws_cdk import (
    aws_ec2 as ec2,
    aws_elasticloadbalancingv2 as elbv2,
    aws_s3 as s3,
    aws_kms as kms,
    aws_iam as iam,
    aws_certificatemanager as acm,
    RemovalPolicy,
)

from .iam_policies import create_alb_s3_access_policy


class MCPNetwork(Construct):
    """
    Network infrastructure for MCP cluster.
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        max_azs: int = 2,
        nat_gateways: int = 1,
        encryption_key: kms.IKey = None,
        account_id: str = None,
        region: str = None,
    ) -> None:
        """
        Initialize the network infrastructure.
        
        Args:
            scope: CDK construct scope
            id: CDK construct ID
            max_azs: Maximum number of availability zones
            nat_gateways: Number of NAT gateways
            encryption_key: KMS key for encryption (optional)
            account_id: AWS account ID
            region: AWS region
        """
        super().__init__(scope, id)

        # Use provided encryption key or create a new one
        self.encryption_key = encryption_key or kms.Key(
            self,
            "EncryptionKey",
            description="KMS key for encrypting MCP Network resources",
            enable_key_rotation=True,
            removal_policy=RemovalPolicy.RETAIN,
            alias=f"{id}-key",
        )

        # Create VPC
        self.vpc = ec2.Vpc(
            self,
            "VPC",
            max_azs=max_azs,
            nat_gateways=nat_gateways,
        )

        # Create ALB Security Group
        self.alb_security_group = ec2.SecurityGroup(
            self,
            "ALBSecurityGroup",
            vpc=self.vpc,
            description="Security group for MCP ALB",
            allow_all_outbound=True,
        )
        
        # Only allow traffic from within the VPC for security
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

        # Create ECS Security Group
        self.ecs_security_group = ec2.SecurityGroup(
            self,
            "ECSSecurityGroup",
            vpc=self.vpc,
            description="Security group for MCP ECS tasks",
            allow_all_outbound=True,
        )
        self.ecs_security_group.add_ingress_rule(
            self.alb_security_group,
            ec2.Port.tcp_range(8000, 9000),
            "Allow traffic from ALB"
        )

        # Create S3 bucket for ALB access logs with proper encryption and policies
        self.access_logs_bucket = s3.Bucket(
            self,
            "AccessLogsBucket",
            encryption=s3.BucketEncryption.KMS,
            encryption_key=self.encryption_key,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.RETAIN,
            versioned=True,  # Enable versioning for audit trail
        )

        # Add bucket policy with proper constraints
        self.access_logs_bucket.add_to_resource_policy(
            create_alb_s3_access_policy(
                self.access_logs_bucket,
                account_id,
                region
            )
        )

        # Create Application Load Balancer with improved security
        self.alb = elbv2.ApplicationLoadBalancer(
            self,
            "ALB",
            vpc=self.vpc,
            internet_facing=True,
            security_group=self.alb_security_group,
            drop_invalid_header_fields=True,  # Security: Drop invalid HTTP headers
        )
        
        # Enable access logging for the ALB
        self.alb.log_access_logs(
            self.access_logs_bucket,
            prefix=f"AWSLogs/{account_id}/elasticloadbalancing/{region}"
        )

        # Create HTTPS listener with TLS 1.2 or higher
        self.listener = self.alb.add_listener(
            "HTTPSListener",
            port=443,
            ssl_policy=elbv2.SslPolicy.TLS12,  # Enforce minimum TLS 1.2
            certificates=[self._create_or_import_certificate()],
            default_action=elbv2.ListenerAction.fixed_response(
                status_code=200,
                content_type="text/plain",
                message_body="HTTPS Endpoint"
            )
        )
        
        # Create HTTP listener that redirects to HTTPS
        self.http_listener = self.alb.add_listener(
            "HTTPListener",
            port=80,
            open=True,
            default_action=elbv2.ListenerAction.redirect(
                protocol="HTTPS",
                port="443",
                host="#{host}",
                path="/#{path}",
                query="#{query}",
                permanent=True
            )
        )
    
    def _create_or_import_certificate(self):
        """
        Create a self-signed certificate for development purposes.
        In production, you would import a real certificate.
        """
        return acm.Certificate(
            self,
            "SelfSignedCertificate",
            domain_name=f"{self.node.id.lower()}.example.com",
            validation=acm.CertificateValidation.from_dns()
        )
