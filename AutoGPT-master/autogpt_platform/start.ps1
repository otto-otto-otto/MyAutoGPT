# AutoGPT Platform - Windows 一键启动脚本
# 用法: 在 autogpt_platform 目录下运行 .\start.ps1

Write-Host "======================================" -ForegroundColor Blue
Write-Host "  AutoGPT Platform - One-Click Start" -ForegroundColor Blue
Write-Host "======================================" -ForegroundColor Blue
Write-Host ""

# 检查 Docker 是否运行
Write-Host "[1/3] Checking prerequisites..." -ForegroundColor Yellow
$dockerRunning = docker info 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker is not running. Please start Docker Desktop first." -ForegroundColor Red
    exit 1
}
Write-Host "  Docker is running." -ForegroundColor Green

# 初始化环境变量文件（如果不存在则从 .default 复制）
Write-Host "[2/3] Initializing environment files..." -ForegroundColor Yellow
if (-not (Test-Path ".env")) {
    Copy-Item ".env.default" ".env" -ErrorAction SilentlyContinue
    Write-Host "  Created .env from .env.default" -ForegroundColor Green
} else {
    Write-Host "  .env already exists, skipping." -ForegroundColor Gray
}

Push-Location "backend"
if (-not (Test-Path ".env")) {
    Copy-Item ".env.default" ".env" -ErrorAction SilentlyContinue
    Write-Host "  Created backend/.env from backend/.env.default" -ForegroundColor Green
} else {
    Write-Host "  backend/.env already exists, skipping." -ForegroundColor Gray
}
Pop-Location

Push-Location "frontend"
if (-not (Test-Path ".env")) {
    Copy-Item ".env.default" ".env" -ErrorAction SilentlyContinue
    Write-Host "  Created frontend/.env from frontend/.env.default" -ForegroundColor Green
} else {
    Write-Host "  frontend/.env already exists, skipping." -ForegroundColor Gray
}
Pop-Location

# 启动所有 Docker 服务
Write-Host "[3/3] Starting all services with Docker Compose..." -ForegroundColor Yellow
Write-Host "  First run may take several minutes to build Docker images..." -ForegroundColor Cyan
Write-Host ""

docker compose up -d

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "======================================" -ForegroundColor Green
    Write-Host "  Startup Complete!" -ForegroundColor Green
    Write-Host "======================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Frontend:  http://localhost:3000" -ForegroundColor Cyan
    Write-Host "  API:       http://localhost:8006" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  View logs:  docker compose logs -f" -ForegroundColor Gray
    Write-Host "  Stop:       docker compose down" -ForegroundColor Gray
    Write-Host "  Stop script: .\stop.ps1" -ForegroundColor Gray
    Write-Host ""
} else {
    Write-Host "ERROR: Docker compose failed to start." -ForegroundColor Red
    Write-Host "Check logs with: docker compose logs" -ForegroundColor Yellow
    exit 1
}
