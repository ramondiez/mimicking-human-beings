"""
Service stack for MCP Cluster CDK project.
"""
import aws_cdk as cdk
from aws_cdk import (
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecr as ecr,
    aws_elasticloadbalancingv2 as elbv2,
    aws_iam as iam,
    aws_logs as logs,
    aws_kms as aws_kms,
    aws_s3 as aws_s3,
    aws_certificatemanager as acm,
    Duration,
    RemovalPolicy,
)
from constructs import Construct
from typing import Dict, Any, List

from mcp_constructs.iam_policies import create_ecs_task_role, create_ecs_execution_role
from mcp_constructs.docker_builder import DockerImageBuilder


class ServiceStack(cdk.Stack):
    """Service stack for MCP Cluster."""

    def __init__(
        self,
        scope: Construct,
        id: str,
        cluster: ecs.ICluster,  # Use existing cluster
        vpc: ec2.IVpc,
        ecs_security_group: ec2.ISecurityGroup,
        alb_security_group: ec2.ISecurityGroup,
        service_config: Dict[str, Any],
        ecs_config: Dict[str, Any],
        lb_config: Dict[str, Any],
        encryption_key: aws_kms.IKey = None,  # Accept an existing KMS key
        **kwargs
    ) -> None:
        """
        Initialize the service stack.
        
        Args:
            scope: CDK construct scope
            id: CDK construct ID
            cluster: Existing ECS cluster
            vpc: VPC for the service
            ecs_security_group: Security group for ECS tasks
            alb_security_group: Security group for ALB
            service_config: Service configuration
            ecs_config: ECS configuration
            lb_config: Load balancer configuration
            encryption_key: KMS key for encryption
            **kwargs: Additional arguments to pass to the parent class
        """
        super().__init__(scope, id, **kwargs)

        # Extract service configuration
        service_name = service_config.get("name")
        dockerfile = service_config.get("dockerfile")
        port = service_config.get("port")
        path_pattern = service_config.get("path_pattern")
        environment = service_config.get("environment", {})
        
        # Extract ECS configuration
        # Updated CPU and memory values to valid combinations
        cpu = ecs_config.get("cpu", 512)  # Valid values: 256, 512, 1024, 2048, 4096
        memory_limit_mib = ecs_config.get("memory_limit_mib", 1024)  # Valid values depend on CPU
        desired_count = ecs_config.get("desired_count", 1)
        auto_scaling = ecs_config.get("auto_scaling", {})
        
        # Extract load balancer configuration
        idle_timeout = lb_config.get("idle_timeout_seconds", 60)
        deletion_protection = lb_config.get("deletion_protection", False)
        http_to_https_redirect = lb_config.get("http_to_https_redirect", True)
        
        # Build and push Docker image
        image_builder = DockerImageBuilder()
        image_builder.login_to_ecr()
        image_uri = image_builder.build_and_push(service_name, dockerfile)
        
        # Create log group with KMS encryption using the provided key or create a new one
        if encryption_key is None:
            # Create a new KMS key if one wasn't provided
            encryption_key = aws_kms.Key(
                self,
                "EncryptionKey",
                description=f"KMS key for encrypting {service_name} resources",
                enable_key_rotation=True,
                removal_policy=RemovalPolicy.DESTROY,
                alias=f"{id}-key",
            )
        
        # Create log group with KMS encryption
        log_group = logs.LogGroup(
            self,
            "LogGroup",
            log_group_name=f"/ecs/{service_name}",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY,
            encryption_key=encryption_key,  # Use the provided or newly created KMS key
        )

        # Create S3 bucket for ALB access logs with appropriate lifecycle rules and encryption
        # Use a bucket name that doesn't rely on tokens that might cause validation issues
        # Generate a unique but deterministic bucket name based on stack name and service name
        stack_name_prefix = self.stack_name.lower().replace("mcp-", "").replace("-", "")[:8]
        service_name_suffix = service_name.lower().replace("-", "")[:8]
        
        access_logs_bucket = aws_s3.Bucket(
            self,
            "AccessLogsBucket",
            # Don't specify bucket_name to let CloudFormation generate a valid unique name
            auto_delete_objects=False,  # Don't automatically delete objects when bucket is deleted
            encryption=aws_s3.BucketEncryption.KMS,  # Use KMS encryption
            encryption_key=encryption_key,  # Use the existing KMS key passed to the constructor
            block_public_access=aws_s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.RETAIN,  # Keep logs even if stack is deleted
            lifecycle_rules=[
                aws_s3.LifecycleRule(
                    id="expire-old-logs",
                    enabled=True,
                    expiration=Duration.days(90),  # Keep logs for 90 days
                    transitions=[
                        aws_s3.Transition(
                            storage_class=aws_s3.StorageClass.INFREQUENT_ACCESS,
                            transition_after=Duration.days(30)
                        ),
                        aws_s3.Transition(
                            storage_class=aws_s3.StorageClass.GLACIER,
                            transition_after=Duration.days(60)
                        )
                    ]
                )
            ]
        )

        # Add bucket policy to allow ALB to write access logs with proper constraints
        access_logs_bucket.add_to_resource_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                principals=[iam.ServicePrincipal("delivery.logs.amazonaws.com")],
                actions=["s3:PutObject"],
                resources=[access_logs_bucket.arn_for_objects(f"AWSLogs/{cdk.Aws.ACCOUNT_ID}/*")],
                conditions={
                    "StringEquals": {
                        "s3:x-amz-acl": "bucket-owner-full-control"
                    }
                }
            )
        )

        # Also add a policy to allow the Elastic Load Balancing service to check bucket permissions
        access_logs_bucket.add_to_resource_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                principals=[iam.ServicePrincipal("logdelivery.elasticloadbalancing.amazonaws.com")],
                actions=["s3:GetBucketAcl", "s3:PutBucketAcl"],
                resources=[access_logs_bucket.bucket_arn]
            )
        )

        # Create Application Load Balancer with access logging enabled
        alb = elbv2.ApplicationLoadBalancer(
            self,
            "ALB",
            vpc=vpc,
            internet_facing=True,
            security_group=alb_security_group,
            load_balancer_name=f"{service_name}-alb",
            idle_timeout=Duration.seconds(idle_timeout),
            deletion_protection=deletion_protection,
            drop_invalid_header_fields=True,  # Drop invalid HTTP headers for security
        )
        
        # Temporarily disable access logging to resolve deployment issues
        # Enable access logging for the ALB only if we have a valid region and HTTPS is enabled
        # env_name = cdk.Stack.of(self).node.try_get_context("environment") or "dev"
        # use_https = env_name != "dev" or lb_config.get("enable_https_in_dev", False)
        # 
        # if cdk.Stack.of(self).region and use_https:
        #     alb.log_access_logs(
        #         access_logs_bucket,
        #         prefix=f"elasticloadbalancing"
        #     )
        # else:
        #     # Log a warning if region is not available or HTTPS is disabled
        print(f"Warning: ALB access logging disabled for {self.stack_name}.")
        
        # Create ECS task execution role with constrained permissions
        execution_role = create_ecs_execution_role(
            self,
            "ExecutionRole",
            service_name,
            encryption_key.key_arn
        )
        
        # Create ECS task role with constrained permissions
        task_role = create_ecs_task_role(
            self,
            "TaskRole",
            service_name
        )
        
        # Create task definition
        task_definition = ecs.FargateTaskDefinition(
            self,
            "TaskDef",
            execution_role=execution_role,
            task_role=task_role,
            cpu=cpu,
            memory_limit_mib=memory_limit_mib,
        )
        
        # Add container to task definition
        container = task_definition.add_container(
            "Container",
            image=ecs.ContainerImage.from_registry(image_uri),
            environment=environment,
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix=service_name,
                log_group=log_group,
            ),
            health_check=ecs.HealthCheck(
                command=["CMD-SHELL", "curl -f http://localhost:$SERVER_PORT/health || exit 1"],
                interval=Duration.seconds(30),
                timeout=Duration.seconds(5),
                retries=3,
                start_period=Duration.seconds(60),
            ),
        )
        
        # Add port mapping
        container.add_port_mappings(
            ecs.PortMapping(
                container_port=port,
                host_port=port,
                protocol=ecs.Protocol.TCP,
            )
        )
        
        # Create service
        self.service = ecs.FargateService(
            self,
            "Service",
            cluster=cluster,  # Use the provided cluster
            task_definition=task_definition,
            desired_count=desired_count,
            security_groups=[ecs_security_group],
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            assign_public_ip=False,
            service_name=f"{service_name}-service",
        )
        
        # Create target group
        target_group = elbv2.ApplicationTargetGroup(
            self,
            "TargetGroup",
            vpc=vpc,
            port=port,
            protocol=elbv2.ApplicationProtocol.HTTP,
            target_type=elbv2.TargetType.IP,
            health_check=elbv2.HealthCheck(
                path="/health",  # Use the health endpoint from MCPBaseServer
                interval=Duration.seconds(30),
                timeout=Duration.seconds(5),
                healthy_threshold_count=2,
                unhealthy_threshold_count=3,
            ),
            target_group_name=f"{service_name}-tg",
        )
        
        # Register service with target group
        self.service.attach_to_application_target_group(target_group)
        
        # Get environment name
        env_name = cdk.Stack.of(self).node.try_get_context("environment") or "dev"
        use_https = env_name != "dev" or lb_config.get("enable_https_in_dev", False)
        
        # Create HTTPS listener only if needed
        if use_https:
            https_listener = alb.add_listener(
                "HttpsListener",
                port=443,
                ssl_policy=elbv2.SslPolicy.TLS12,  # Enforce minimum TLS 1.2
                certificates=[self._create_or_import_certificate(lb_config)],
                default_action=elbv2.ListenerAction.forward([target_group])
            )
        
        # Always create HTTP listener
        http_listener = alb.add_listener(
            "HttpListener",
            port=80,
            # Set open=False to avoid allowing traffic from 0.0.0.0/0
            open=False,
            default_action=(
                elbv2.ListenerAction.redirect(
                    protocol="HTTPS",
                    port="443",
                    host="#{host}",
                    path="/#{path}",
                    query="#{query}",
                    permanent=True
                ) if use_https and lb_config.get("http_to_https_redirect", True)
                else elbv2.ListenerAction.forward([target_group])
            )
        )
        
        # Add specific security group rules for HTTP listener
        # This restricts HTTP access to specific sources instead of 0.0.0.0/0
        http_listener.connections.allow_default_port_from(
            ec2.Peer.ipv4(vpc.vpc_cidr_block),
            "Allow HTTP from within VPC only"
        )
        
        # Set up auto scaling if enabled
        if auto_scaling.get("enabled", False):
            scaling = self.service.auto_scale_task_count(
                min_capacity=auto_scaling.get("min_capacity", 1),
                max_capacity=auto_scaling.get("max_capacity", 4),
            )
            
            scaling.scale_on_cpu_utilization(
                "CpuScaling",
                target_utilization_percent=auto_scaling.get("target_cpu_utilization", 70),
                scale_in_cooldown=Duration.seconds(60),
                scale_out_cooldown=Duration.seconds(60),
            )
        
        # Store the service URL for reference by other stacks
        env_name = cdk.Stack.of(self).node.try_get_context("environment") or "dev"
        use_https = env_name != "dev" or lb_config.get("enable_https_in_dev", False)
        
        if use_https:
            self.service_url = f"https://{alb.load_balancer_dns_name}"
        else:
            self.service_url = f"http://{alb.load_balancer_dns_name}"
        
        # Outputs
        cdk.CfnOutput(
            self,
            "ServiceName",
            value=self.service.service_name,
            description=f"{service_name} service name",
            export_name=f"{id}-service-name",
        )
        
        cdk.CfnOutput(
            self,
            "LoadBalancerDNS",
            value=alb.load_balancer_dns_name,
            description=f"{service_name} load balancer DNS name",
            export_name=f"{id}-lb-dns",
        )
        
        cdk.CfnOutput(
            self,
            "ServiceURL",
            value=self.service_url,
            description=f"{service_name} service URL",
            export_name=f"{id}-service-url",
        )
    
    def _create_or_import_certificate(self, lb_config: Dict[str, Any]):
        """
        Create or import a certificate for HTTPS.
        
        Args:
            lb_config: Load balancer configuration
            
        Returns:
            ICertificate: The certificate to use with the ALB
        """
        env_name = cdk.Stack.of(self).node.try_get_context("environment") or "dev"
        
        # For development, return a dummy certificate reference that won't be used
        # since we'll only use HTTP in development
        if env_name == "dev" and not lb_config.get("enable_https_in_dev", False):
            return acm.Certificate.from_certificate_arn(
                self,
                "DummyCertificate",
                certificate_arn="arn:aws:acm:us-east-1:123456789012:certificate/00000000-0000-0000-0000-000000000000"
            )
        
        # For production or if HTTPS is explicitly enabled in dev
        certificate_arn = lb_config.get("certificate_arn")
        domain_name = lb_config.get("domain_name")
        create_certificate = lb_config.get("create_certificate", False)
        
        if certificate_arn:
            # Use an existing certificate
            return acm.Certificate.from_certificate_arn(
                self, 
                "ImportedCertificate",
                certificate_arn=certificate_arn
            )
        elif create_certificate and domain_name:
            # Create a new certificate with email validation
            return acm.Certificate(
                self,
                "Certificate",
                domain_name=domain_name,
                validation=acm.CertificateValidation.from_email()
            )
        else:
            # Create a default certificate with email validation
            domain_name = domain_name or f"{self.stack_name.lower()}.example.com"
            return acm.Certificate(
                self,
                "SelfSignedCertificate",
                domain_name=domain_name,
                validation=acm.CertificateValidation.from_email()
            )
