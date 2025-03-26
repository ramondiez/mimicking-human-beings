#!/usr/bin/env python3
"""
Main CDK application for MCP cluster.
"""
import aws_cdk as cdk
from stacks.network_stack import NetworkStack
from stacks.cluster_stack import ClusterStack
from stacks.service_stack import ServiceStack
from stacks.client_stack import ClientStack
from stacks.key_stack import KeyStack  # Import the new key stack
from config.config_loader import ConfigLoader
from config.environment import Environment


def main():
    """
    Main entry point for the CDK application.
    """
    app = cdk.App()
    
    # Get environment name from context
    env_name = app.node.try_get_context("environment") or "dev"
    
    # Load configuration
    config_loader = ConfigLoader()
    vpc_config = config_loader.get_vpc_config(env_name)
    ecs_config = config_loader.get_ecs_config(env_name)
    lambda_config = config_loader.get_lambda_config(env_name) or {}  # Ensure lambda_config is never None
    lb_config = config_loader.get_load_balancer_config(env_name)
    
    # Get service configurations
    services = Environment.get_services()
    
    # Create key stack first (for encryption)
    key_stack = KeyStack(
        app,
        f"MCP-Key-{env_name}",
        env=config_loader.get_cdk_environment(),
    )
    
    # Create network stack
    network_stack = NetworkStack(
        app,
        f"MCP-Network-{env_name}",
        vpc_config=vpc_config,
        env=config_loader.get_cdk_environment(),
    )
    
    # Create cluster stack
    cluster_stack = ClusterStack(
        app,
        f"MCP-Cluster-{env_name}",
        vpc=network_stack.vpc,
        env=config_loader.get_cdk_environment(),
    )
    
    # Add dependency on network stack
    cluster_stack.add_dependency(network_stack)
    
    # Create service stacks
    service_stacks = {}
    
    # Create url-fetcher service stack
    url_fetcher_stack = ServiceStack(
        app,
        f"MCP-Url-fetcher-{env_name}",
        cluster=cluster_stack.cluster,
        vpc=network_stack.vpc,
        ecs_security_group=network_stack.ecs_security_group,
        alb_security_group=network_stack.alb_security_group,
        service_config=services["url-fetcher"],
        ecs_config=ecs_config,
        lb_config=lb_config,
        encryption_key=key_stack.encryption_key,  # Pass the encryption key
        env=config_loader.get_cdk_environment(),
    )
    url_fetcher_stack.add_dependency(cluster_stack)
    url_fetcher_stack.add_dependency(key_stack)  # Add dependency on key stack
    service_stacks["url-fetcher"] = url_fetcher_stack

    # Create random-web service stack
    random_web_stack = ServiceStack(
        app,
        f"MCP-Random-web-{env_name}",
        cluster=cluster_stack.cluster,
        vpc=network_stack.vpc,
        ecs_security_group=network_stack.ecs_security_group,
        alb_security_group=network_stack.alb_security_group,
        service_config=services["random-web"],
        ecs_config=ecs_config,
        lb_config=lb_config,
        encryption_key=key_stack.encryption_key,  # Pass the encryption key
        env=config_loader.get_cdk_environment(),
    )
    random_web_stack.add_dependency(cluster_stack)
    random_web_stack.add_dependency(key_stack)  # Add dependency on key stack
    service_stacks["random-web"] = random_web_stack

    # Create explicit service URLs dictionary with the correct environment variable names
    service_urls = {
        "URL_FETCHER_URL": url_fetcher_stack.service_url,
        "RANDOM_WEB_URL": random_web_stack.service_url
    }
    
    # Create client stack with direct references to service stacks
    client_stack = ClientStack(
        app,
        f"MCP-Client-{env_name}",
        vpc=network_stack.vpc,
        lambda_security_group=network_stack.lambda_security_group,
        lambda_config=lambda_config,
        url_fetcher_stack=url_fetcher_stack,  # Pass the stack directly
        random_web_stack=random_web_stack,    # Pass the stack directly
        encryption_key=key_stack.encryption_key,  # Pass the encryption key
        env=config_loader.get_cdk_environment(),
    )
    
    # Add dependency on service stacks and key stack
    for service_stack in service_stacks.values():
        client_stack.add_dependency(service_stack)
    client_stack.add_dependency(key_stack)  # Add dependency on key stack
    
    # Add tags to all resources
    cdk.Tags.of(app).add("Project", "MCP-Cluster")
    cdk.Tags.of(app).add("Environment", env_name)
    
    app.synth()


if __name__ == "__main__":
    main()
