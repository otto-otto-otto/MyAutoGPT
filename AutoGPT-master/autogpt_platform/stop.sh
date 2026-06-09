#!/bin/bash
# AutoGPT Platform - Linux/Mac 停止脚本

echo -e "\033[1;33mStopping AutoGPT Platform...\033[0m"
docker compose down
echo -e "\033[0;32mAll services stopped.\033[0m"
