#!/bin/bash
# CI/CD Pipeline Script
# Runs tests, linting, and builds Docker image

set -e  # Exit on error

echo "=== Adventure MUD CI/CD Pipeline ==="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Step 1: Code quality checks
echo -e "${YELLOW}Step 1: Running code quality checks...${NC}"

echo "Running ruff..."
if ruff check app/ tests/ scripts/; then
    echo -e "${GREEN}✓ Ruff passed${NC}"
else
    echo -e "${RED}✗ Ruff failed${NC}"
    exit 1
fi

echo "Running black check..."
if black --check app/ tests/ scripts/; then
    echo -e "${GREEN}✓ Black formatting check passed${NC}"
else
    echo -e "${RED}✗ Black formatting check failed${NC}"
    echo "Run: black app/ tests/ scripts/ to fix formatting"
    exit 1
fi

# Step 2: Run tests
echo ""
echo -e "${YELLOW}Step 2: Running tests...${NC}"

if python -m pytest tests/ -v --cov=app --cov-report=term-missing; then
    echo -e "${GREEN}✓ Tests passed${NC}"
else
    echo -e "${RED}✗ Tests failed${NC}"
    exit 1
fi

# Step 3: Check exception handling
echo ""
echo -e "${YELLOW}Step 3: Checking exception handling...${NC}"

if python scripts/fix_exception_handling.py --check; then
    echo -e "${GREEN}✓ No silent exception handlers found${NC}"
else
    echo -e "${YELLOW}⚠ Silent exception handlers found (see report)${NC}"
    # Don't fail build, just warn
fi

# Step 4: Build Docker image
echo ""
echo -e "${YELLOW}Step 4: Building Docker image...${NC}"

IMAGE_TAG="adventure-mud:$(date +%Y%m%d-%H%M%S)"

if docker build -t adventure-mud:latest -t "$IMAGE_TAG" .; then
    echo -e "${GREEN}✓ Docker image built: $IMAGE_TAG${NC}"
else
    echo -e "${RED}✗ Docker build failed${NC}"
    exit 1
fi

# Step 5: Test Docker image
echo ""
echo -e "${YELLOW}Step 5: Testing Docker image...${NC}"

# Start a test container
CONTAINER_ID=$(docker run -d -e DATABASE_URL=sqlite:///test.db adventure-mud:latest python -c "print('Container ready')")

# Wait a moment for container to start
sleep 2

# Check if container is still running
if docker ps | grep -q "$CONTAINER_ID"; then
    echo -e "${GREEN}✓ Docker container started successfully${NC}"
    docker stop "$CONTAINER_ID" > /dev/null
    docker rm "$CONTAINER_ID" > /dev/null
else
    echo -e "${RED}✗ Docker container failed to start${NC}"
    docker logs "$CONTAINER_ID"
    docker rm "$CONTAINER_ID" > /dev/null
    exit 1
fi

echo ""
echo -e "${GREEN}=== All checks passed! ===${NC}"
echo ""
echo "Next steps:"
echo "  - Push to git: git push origin main"
echo "  - Deploy: docker-compose up -d"
echo "  - Tag release: git tag v1.0.0 && git push --tags"
