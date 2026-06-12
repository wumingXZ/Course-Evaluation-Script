@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: ============================================================
:: 复旦大学课评自动填写工具 — Windows 启动脚本
:: 双击此文件即可运行，首次运行会自动安装依赖
:: ============================================================

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"
set "VENV_DIR=%SCRIPT_DIR%venv"

echo ========================================
echo   复旦大学课评自动填写工具
echo   Course Evaluation Script
echo ========================================
echo.

:: ── Python 检测 ──────────────────────────────────────────
set "PYTHON="

:: 尝试 python
where python >nul 2>nul
if %ERRORLEVEL% equ 0 (
    for /f "tokens=2 delims=." %%a in ('python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2^>nul') do (
        set "PYVER=%%a"
    )
    python -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
    if !ERRORLEVEL! equ 0 set "PYTHON=python"
)

:: 尝试 python3
if "%PYTHON%"=="" (
    where python3 >nul 2>nul
    if %ERRORLEVEL% equ 0 (
        python3 -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
        if !ERRORLEVEL! equ 0 set "PYTHON=python3"
    )
)

:: 尝试 py launcher
if "%PYTHON%"=="" (
    where py >nul 2>nul
    if %ERRORLEVEL% equ 0 (
        py -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
        if !ERRORLEVEL! equ 0 set "PYTHON=py"
    )
)

if "%PYTHON%"=="" (
    echo ┌─────────────────────────────────────────────┐
    echo │  X 未找到 Python 3.10 或更高版本              │
    echo │                                             │
    echo │  请先安装 Python：                           │
    echo │  https://www.python.org/downloads/           │
    echo │                                             │
    echo │  安装时务必勾选 "Add Python to PATH"         │
    echo └─────────────────────────────────────────────┘
    echo.
    pause
    exit /b 1
)

echo [INFO] 使用 Python: %PYTHON%

:: ── 虚拟环境 ─────────────────────────────────────────────
if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo.
    echo ┌─────────────────────────────────────────────┐
    echo │  ^>^> 首次运行，正在创建虚拟环境...            │
    echo │  所有依赖安装在项目文件夹内，不会污染系统       │
    echo └─────────────────────────────────────────────┘
    echo.

    %PYTHON% -m venv "%VENV_DIR%"
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] 创建虚拟环境失败，请检查 Python 安装
        pause
        exit /b 1
    )

    call "%VENV_DIR%\Scripts\activate.bat"

    echo [INFO] 正在安装 Python 依赖...
    pip install --upgrade pip --quiet
    pip install -r requirements.txt --quiet
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] 依赖安装失败，请检查网络连接后重试
        pause
        exit /b 1
    )
    echo [INFO] Python 依赖安装完成 √

    echo [INFO] 正在安装 Playwright 浏览器（可能需要几分钟）...
    python -m playwright install chromium
    if %ERRORLEVEL% neq 0 (
        echo [WARN] Playwright 浏览器安装失败
        echo        可稍后手动运行: python -m playwright install chromium
    ) else (
        echo [INFO] Playwright 浏览器安装完成 √
    )

    echo.
    echo ┌─────────────────────────────────────────────┐
    echo │  √ 环境安装完成！                            │
    echo └─────────────────────────────────────────────┘
    echo.
) else (
    call "%VENV_DIR%\Scripts\activate.bat"
    echo [INFO] 使用已有虚拟环境
)

:: ── 运行主程序 ───────────────────────────────────────────
echo.
echo [INFO] 启动课评脚本...
echo   提示：使用 -1 -y 参数可直接全自动运行
echo   用法：在 cmd 中执行 start.bat -1 -y --headless
echo.

python main.py %*
set EXIT_CODE=%ERRORLEVEL%

:: ── 保持窗口打开 ─────────────────────────────────────────
echo.
echo ========================================
if %EXIT_CODE% equ 0 (
    echo   脚本执行完成
) else (
    echo   脚本异常退出 (exit code: %EXIT_CODE%)
)
echo ========================================
pause
exit /b %EXIT_CODE%
