# AutoGPT Platform - Windows 停止脚本
# 用法: 在 autogpt_platform 目录下运行 .\stop.ps1

Write-Host "Stopping AutoGPT Platform..." -ForegroundColor Yellow
docker compose down
Write-Host "All services stopped." -ForegroundColor Green
