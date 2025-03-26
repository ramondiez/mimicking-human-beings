#!/bin/bash

# Script to set up git hooks for the project

# Get the project root directory
PROJECT_ROOT=$(git rev-parse --show-toplevel)

# Create hooks directory if it doesn't exist
mkdir -p "$PROJECT_ROOT/.git/hooks"

# Create pre-commit hook
cat > "$PROJECT_ROOT/.git/hooks/pre-commit" << 'EOF'
#!/bin/bash

# Pre-commit hook to run Checkov security checks on CDK code

# Get the project root directory
PROJECT_ROOT=$(git rev-parse --show-toplevel)

echo "Running Checkov security checks..."

# Change to the project directory
cd "$PROJECT_ROOT"

# Parse the .checkov.yaml file to get skip checks
if [ -f "$PROJECT_ROOT/.checkov.yaml" ]; then
    echo "Parsing .checkov.yaml for skip checks..."
    # Extract skip-checks from the YAML file, removing comments and whitespace
    SKIP_CHECKS=$(grep -A 100 "skip-checks:" "$PROJECT_ROOT/.checkov.yaml" | grep -v "skip-checks:" | grep "^  - " | sed 's/^  - //' | sed 's/#.*$//' | tr -d ' ' | tr '\n' ',' | sed 's/,$//')
    
    if [ -z "$SKIP_CHECKS" ]; then
        # Try alternative format (skip-check)
        SKIP_CHECKS=$(grep -A 100 "skip-check:" "$PROJECT_ROOT/.checkov.yaml" | grep -v "skip-check:" | grep "^  - " | sed 's/^  - //' | sed 's/#.*$//' | tr -d ' ' | tr '\n' ',' | sed 's/,$//')
    fi
    
    if [ -n "$SKIP_CHECKS" ]; then
        echo "Found skip checks: $SKIP_CHECKS"
        SKIP_CHECK_PARAM="--skip-check $SKIP_CHECKS"
    else
        echo "No skip checks found in .checkov.yaml"
        SKIP_CHECK_PARAM=""
    fi
else
    echo "No .checkov.yaml file found"
    SKIP_CHECK_PARAM=""
fi

# Synthesize CDK code
echo "Synthesizing CDK code..."
cd cdk && cdk synth
cd "$PROJECT_ROOT"

if [ $? -ne 0 ]; then
    echo "❌ CDK synthesis failed. Fix the errors before committing."
    exit 1
fi

# Run Checkov on the synthesized CloudFormation templates with parsed skip checks
echo "Running Checkov on CloudFormation templates..."
echo "Skip checks: $SKIP_CHECK_PARAM"
checkov -d cdk/cdk.out/ --framework cloudformation $SKIP_CHECK_PARAM

if [ $? -ne 0 ]; then
    echo "❌ Checkov found security issues. Please fix them before committing."
    exit 1
fi

# Run Checkov on Docker files with parsed skip checks
if [ -d "$PROJECT_ROOT/docker" ]; then
    echo "Running Checkov on Docker files..."
    checkov -d docker/ --framework dockerfile $SKIP_CHECK_PARAM
    
    if [ $? -ne 0 ]; then
        echo "❌ Checkov found security issues in Docker files. Please fix them before committing."
        exit 1
    fi
fi

echo "✅ Checkov security checks passed!"

exit 0
EOF

# Make the hook executable
chmod +x "$PROJECT_ROOT/.git/hooks/pre-commit"

# Install Checkov if not already installed
if ! command -v checkov &> /dev/null; then
    echo "Installing Checkov..."
    pip install checkov
fi

echo "Git hooks have been set up successfully!"
echo "Checkov will now run automatically before each commit using skip checks from .checkov.yaml"
