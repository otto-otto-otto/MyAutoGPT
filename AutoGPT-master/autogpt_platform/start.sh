#!/bin/bash
# AutoGPT Platform - Linux/Mac 一键启动脚本
# 用法: 在 autogpt_platform 目录下运行 ./start.sh

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  AutoGPT Platform - One-Click Start${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check Docker
echo -e "${YELLOW}[1/3] Checking prerequisites...${NC}"
if ! docker info &> /dev/null; then
    echo -e "${RED}ERROR: Docker is not running. Please start Docker first.${NC}"
    exit 1
fi
echo -e "${GREEN}  Docker is running.${NC}"

# Initialize env files
echo -e "${YELLOW}[2/3] Initializing environment files...${NC}"
cp -n .env.default .env 2>/dev/null && echo -e "${GREEN}  Created .env${NC}" || echo -e "  .env already exists, skipping."
cp -n backend/.env.default backend/.env 2>/dev/null && echo -e "${GREEN}  Created backend/.env${NC}" || echo -e "  backend/.env already exists, skipping."
cp -n frontend/.env.default frontend/.env 2>/dev/null && echo -e "${GREEN}  Created frontend/.env${NC}" || echo -e "  frontend/.env already exists, skipping."

# Start services
echo -e "${YELLOW}[3/3] Starting all services with Docker Compose...${NC}"
echo -e "${CYAN}  First run may take several minutes to build Docker images...${NC}"
echo ""

docker compose up -d

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Startup Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "  Frontend:  ${CYAN}http://localhost:3000${NC}"
echo -e "  API:       ${CYAN}http://localhost:8006${NC}"
echo ""
echo -e "  View logs:  docker compose logs -f"
echo -e "  Stop:       make stop  or  docker compose down"
echo ""
