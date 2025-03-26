"""
ECS service construct for MCP servers.
"""
from constructs import Construct
from aws_cdk import (
    Duration,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_logs as logs,
    aws_iam as iam,
    aws_elasticloadbalancingv2 as elbv2,
    RemovalPolicy,
)


class MCPService(Construct):
    """
    Construct for creating an MCP service on ECS.
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        cluster: ecs.ICluster,
        vpc: ec2.IVpc,
        execution_role: iam.IRole,
        security_group: ec2.ISecurityGroup,
        listener: elbv2.IApplicationListener,
        name: str,
        image_uri: str,
        port: int,
        path_pattern: str,
        environment: dict,
        cpu: int = 256,
        memory_limit_mib: int = 512,
        desired_count: int = 1,
        health_check_path: str = "/health",
    ) -> None:
        """
        Initialize the MCP service.
        
        Args:
            scope: CDK construct scope
            id: CDK construct ID
            cluster: ECS cluster
            vpc: VPC for the service
            execution_role: IAM role for task execution
            security_group: Security group for the service
            listener: ALB listener
            name: Service name
            image_uri: Docker image URI
            port: Container port
            path_pattern: ALB path pattern for routing
            environment: Environment variables
            cpu: CPU units for the task
            memory_limit_mib: Memory limit in MiB
            desired_count: Desired count of tasks
            health_check_path: Health check path
        """
        super().__init__(scope, id)

        # Create log group
        log_group = logs.LogGroup(
            self,
            f"LogGroup",
            log_group_name=f"/ecs/{name}-server",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Create task definition
        task_definition = ecs.FargateTaskDefinition(
            self,
            f"TaskDef",
            execution_role=execution_role,
            cpu=cpu,
            memory_limit_mib=memory_limit_mib,
        )

        # Add container to task definition
        container = task_definition.add_container(
            "Container",
            image=ecs.ContainerImage.from_registry(image_uri),
            environment=environment,
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix=name,
                log_group=log_group,
            ),
            health_check=ecs.HealthCheck(
                command=["CMD-SHELL", f"curl -f http://localhost:{port}/health || exit 1"],
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
            cluster=cluster,
            task_definition=task_definition,
            desired_count=desired_count,
            security_groups=[security_group],
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_NAT),
            assign_public_ip=False,
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
                path=health_check_path,
                interval=Duration.seconds(30),
                timeout=Duration.seconds(5),
                healthy_threshold_count=2,
                unhealthy_threshold_count=3,
            ),
        )

        # Register service with target group
        self.service.attach_to_application_target_group(target_group)

        # Add routing rule to listener
        listener.add_action(
            f"Route",
            conditions=[
                elbv2.ListenerCondition.path_patterns([path_pattern])
            ],
            priority=len(listener.node.children) + 1,
            action=elbv2.ListenerAction.forward([target_group]),
        )