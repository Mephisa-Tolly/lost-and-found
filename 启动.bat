@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title 校园智能失物招领匹配系统 v3.0
cd /d "%~dp0"

echo ============================================================
echo   校园智能失物招领匹配系统  v3.0
echo ============================================================
echo.

REM ---------- 1. 找 Python ----------
set "PY="
python --version >nul 2>&1 && set "PY=python"
if not defined PY (
    py -3 --version >nul 2>&1 && set "PY=py -3"
)
if not defined PY (
    python3 --version >nul 2>&1 && set "PY=python3"
)

if not defined PY (
    echo [错误] 这台电脑上没有找到 Python。
    echo.
    echo   请先安装 Python 3.9 或更高版本：
    echo     https://www.python.org/downloads/
    echo.
    echo   安装时务必勾选  "Add Python to PATH"  （在安装界面最下面）
    echo   安装完成后重新双击本文件即可。
    echo.
    pause
    exit /b 1
)

for /f "delims=" %%v in ('%PY% -c "import sys;print(sys.version.split()[0])"') do set "PYVER=%%v"
echo [1/4] Python %PYVER%   OK

REM ---------- 2. 检查/安装依赖 ----------
%PY% -c "import fastapi, uvicorn" >nul 2>&1
if errorlevel 1 (
    echo [2/4] 首次运行，正在安装依赖（约 1-3 分钟，需要联网）……
    echo       如果很慢，是网络问题，换个网络再试一次即可。
    %PY% -m pip install -r backend\requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --quiet
    if errorlevel 1 (
        echo.
        echo [错误] 依赖安装失败。请检查网络后重新双击本文件。
        pause
        exit /b 1
    )
    echo       依赖安装完成
) else (
    echo [2/4] 依赖已就绪   OK
)

REM ---------- 3. 准备数据 ----------
if not exist "frontend\dist\index.html" (
    where npm >nul 2>&1
    if errorlevel 1 (
        echo [提示] 未找到 frontend\dist，本机也没装 Node.js，页面将无法打开。
        echo        请安装 Node.js 20+ 后执行：cd frontend ^&^& npm install ^&^& npm run build
    ) else (
        echo [2.5/4] 正在构建前端（首次约 1-2 分钟）……
        pushd frontend
        call npm install --no-audit --no-fund
        call npm run build
        popd
    )
)

if not exist "backend\lost_found.db" (
    echo [3/4] 首次运行，正在创建数据库……
) else (
    echo [3/4] 数据库已存在，保留原有数据
)

REM ---------- 4. 启动 ----------
echo [4/4] 正在启动服务……
echo.
echo ------------------------------------------------------------
echo   启动后浏览器会自动打开。也可以手动访问：
echo     http://localhost:8000
echo.
echo   给同一局域网的其他人访问：http://你的IP:8000
echo   （本机 IP 见下面打印的 IP 地址）
echo.
echo   关闭服务：直接关掉这个窗口
echo ------------------------------------------------------------
echo.

REM 3 秒后自动开浏览器（等服务起来）
start "" /b cmd /c "timeout /t 4 >nul & start http://localhost:8000"

cd backend
%PY% main.py

echo.
echo 服务已停止。
pause
