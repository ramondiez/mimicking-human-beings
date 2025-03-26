"""
Docker image builder construct for ECR.
"""
import os
import subprocess

# No need to import Construct here as it's not used in this class
# This avoids the circular import issue


class DockerImageBuilder:
    """
    Helper class to build and push Docker images to ECR.
    """
    
    def __init__(self):
        # Get AWS account ID and region
        self.account_id = subprocess.check_output(
            ["aws", "sts", "get-caller-identity", "--query", "Account", "--output", "text"]
        ).decode("utf-8").strip()
        
        self.region = subprocess.check_output(
            ["aws", "configure", "get", "region"]
        ).decode("utf-8").strip() or "us-east-1"  # Default to us-east-1 if not set
        
        self.project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    
    def ensure_repository(self, repo_name: str) -> str:
        """
        Ensure ECR repository exists.
        
        Args:
            repo_name: Repository name (e.g., "mcp/url-fetcher")
            
        Returns:
            Repository URI
        """
        try:
            # Check if repository exists
            subprocess.check_output(
                ["aws", "ecr", "describe-repositories", "--repository-names", repo_name],
                stderr=subprocess.DEVNULL
            )
        except subprocess.CalledProcessError:
            # Create repository if it doesn't exist
            print(f"Creating ECR repository: {repo_name}")
            subprocess.check_call(
                ["aws", "ecr", "create-repository", "--repository-name", repo_name]
            )
        
        return f"{self.account_id}.dkr.ecr.{self.region}.amazonaws.com/{repo_name}"
    
    def login_to_ecr(self):
        """
        Login to ECR.
        """
        print("Logging in to ECR...")
        password = subprocess.check_output(
            ["aws", "ecr", "get-login-password"]
        )
        
        login_proc = subprocess.Popen(
            ["docker", "login", "--username", "AWS", "--password-stdin", 
             f"{self.account_id}.dkr.ecr.{self.region}.amazonaws.com"],
            stdin=subprocess.PIPE
        )
        login_proc.communicate(input=password)
        
        if login_proc.returncode != 0:
            raise Exception("Failed to login to ECR")
    
    def build_and_push(self, name: str, dockerfile_path: str) -> str:
        """
        Build and push Docker image to ECR.
        
        Args:
            name: Image name (e.g., "url-fetcher")
            dockerfile_path: Path to Dockerfile relative to project root
            
        Returns:
            Repository URI with image tag
        """
        repo_name = f"mcp/{name}"
        repo_uri = self.ensure_repository(repo_name)
        image_uri = f"{repo_uri}:latest"
        
        print(f"Building {name} image...")
        dockerfile_full_path = os.path.join(self.project_root, dockerfile_path)
        
        subprocess.check_call(
            ["docker", "build", "--platform=linux/amd64", "-t", image_uri, "-f", dockerfile_full_path, self.project_root]
        )
        
        print(f"Pushing {name} image to ECR...")
        subprocess.check_call(
            ["docker", "push", image_uri]
        )
        
        return image_uri
