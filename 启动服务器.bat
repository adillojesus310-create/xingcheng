@echo off
chcp 65001 >nul
title 📋 行程小程序服务器
echo =============================================
echo   📋 行程小程序 - 服务器启动中...
echo =============================================
echo.
echo 正在检查 Python...

where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ❌ 找不到 Python！请先安装 Python
    echo 下载地址: https://www.python.org/downloads/
    echo 安装时记得勾选 "Add Python to PATH"
    pause
    exit /b
)

python --version
echo ✅ Python 已就绪
echo.

echo 启动服务器...
start "" http://localhost:8765
python "%CD%\server.py" 8765

pause
