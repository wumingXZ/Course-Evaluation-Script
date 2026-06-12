@echo off
chcp 65001 >nul 2>nul
setlocal enabledelayedexpansion

:: ============================================================
:: 复旦大学课评自动填写工具 — Windows 启动脚本
:: 双击此文件即可运行，首次运行会自动安装依赖
::
:: 两种使用方式：
::   1. 双击 → 交互式菜单引导配置
::   2. cmd 中执行 start.bat -1 -y → 直接透传参数（专家模式）
:: ============================================================

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"
set "VENV_DIR=%SCRIPT_DIR%venv"

:: ── 生成 ANSI ESC 字符 ───────────────────────────────────
for /f %%a in ('echo prompt $E ^| cmd') do set "ESC=%%a"
set "BOLD=%ESC%[1m"
set "GREEN=%ESC%[32m"
set "YELLOW=%ESC%[33m"
set "CYAN=%ESC%[36m"
set "RED=%ESC%[31m"
set "RESET=%ESC%[0m"

:: ── 横幅 ──────────────────────────────────────────────────
echo.
echo %CYAN%%BOLD%╔════════════════════════════════════════════╗%RESET%
echo %CYAN%%BOLD%║    复旦大学课评自动填写工具                 ║%RESET%
echo %CYAN%%BOLD%║    Course Evaluation Script                ║%RESET%
echo %CYAN%%BOLD%╚════════════════════════════════════════════╝%RESET%
echo.

:: ── Python 检测 ──────────────────────────────────────────
set "PYTHON="

where python >nul 2>nul
if !ERRORLEVEL! equ 0 (
    python -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
    if !ERRORLEVEL! equ 0 set "PYTHON=python"
)

if "%PYTHON%"=="" (
    where python3 >nul 2>nul
    if !ERRORLEVEL! equ 0 (
        python3 -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
        if !ERRORLEVEL! equ 0 set "PYTHON=python3"
    )
)

if "%PYTHON%"=="" (
    where py >nul 2>nul
    if !ERRORLEVEL! equ 0 (
        py -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
        if !ERRORLEVEL! equ 0 set "PYTHON=py"
    )
)

if "%PYTHON%"=="" (
    echo %RED%%BOLD%┌─────────────────────────────────────────────┐%RESET%
    echo %RED%%BOLD%│  X 未找到 Python 3.10 或更高版本              │%RESET%
    echo %RED%%BOLD%│                                             │%RESET%
    echo %RED%%BOLD%│  请先安装 Python：                           │%RESET%
    echo %RED%%BOLD%│  https://www.python.org/downloads/           │%RESET%
    echo %RED%%BOLD%│                                             │%RESET%
    echo %RED%%BOLD%│  安装时务必勾选 "Add Python to PATH"         │%RESET%
    echo %RED%%BOLD%└─────────────────────────────────────────────┘%RESET%
    echo.
    pause
    exit /b 1
)

:: ── 虚拟环境 ─────────────────────────────────────────────
if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo.
    echo %GREEN%┌─────────────────────────────────────────────┐%RESET%
    echo %GREEN%│  ^>^> 首次运行，正在创建虚拟环境...            │%RESET%
    echo %GREEN%│  所有依赖安装在项目文件夹内，不会污染系统       │%RESET%
    echo %GREEN%└─────────────────────────────────────────────┘%RESET%
    echo.

    %PYTHON% -m venv "%VENV_DIR%"
    if !ERRORLEVEL! neq 0 (
        echo %RED%[ERROR] 创建虚拟环境失败，请检查 Python 安装%RESET%
        pause
        exit /b 1
    )

    call "%VENV_DIR%\Scripts\activate.bat"

    echo [INFO] 正在安装 Python 依赖...
    pip install --upgrade pip --quiet
    pip install -r requirements.txt --quiet
    if !ERRORLEVEL! neq 0 (
        echo %RED%[ERROR] 依赖安装失败，请检查网络连接后重试%RESET%
        pause
        exit /b 1
    )
    echo [INFO] Python 依赖安装完成 √

    echo [INFO] 正在安装 Playwright 浏览器（可能需要几分钟）...
    python -m playwright install chromium
    if !ERRORLEVEL! neq 0 (
        echo %YELLOW%[WARN] Playwright 浏览器安装失败%RESET%
        echo        可稍后手动运行: python -m playwright install chromium
    ) else (
        echo [INFO] Playwright 浏览器安装完成 √
    )

    echo.
    echo %GREEN%%BOLD%┌─────────────────────────────────────────────┐%RESET%
    echo %GREEN%%BOLD%│  √ 环境安装完成！                            │%RESET%
    echo %GREEN%%BOLD%└─────────────────────────────────────────────┘%RESET%
    echo.
) else (
    call "%VENV_DIR%\Scripts\activate.bat"
)

:: ── 主流程 ───────────────────────────────────────────────

:: 如果有命令行参数，直接透传（专家模式）
if not "%~1"=="" (
    echo %BOLD%[INFO] 专家模式：参数透传到 main.py%RESET%
    echo [INFO] 命令行: python main.py %*
    echo.
    python main.py %*
    set EXIT_CODE=!ERRORLEVEL!
    goto :end_script
)

:: ── 交互式菜单模式 ───────────────────────────────────────
echo %YELLOW%⚠️  免责声明：本项目仅用于学习用途，使用者自行承担一切后果。%RESET%
echo.
echo 欢迎使用课评自动填写工具！
echo 下面将通过几个简单问题配置运行参数。
echo.

:: ── 问题 1：情感模式 ─────────────────────────────────────
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.
echo %YELLOW%请选择评价策略（情感模式）：%RESET%
echo   %BOLD%[1]%RESET% 全部喜欢 — 以「非常同意」「同意」为主
echo   %BOLD%[2]%RESET% 全部一般 — 以「一般」「中等」为主
echo   %BOLD%[3]%RESET% 全部讨厌 — 以「非常不同意」「不同意」为主
echo   %BOLD%[4]%RESET% 每门课单独选择 — 进入每门课时手动选择
echo.
choice /c 1234 /n /m "请输入选项 (1-4): "
set SENTIMENT_CHOICE=%ERRORLEVEL%

echo.
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.

:: ── 问题 2：是否显示浏览器 ──────────────────────────────
echo %YELLOW%是否显示浏览器窗口？%RESET%
echo   %BOLD%[1]%RESET% 是 — 显示窗口（可以看到填写过程）
echo   %BOLD%[2]%RESET% 否 — 隐藏窗口（后台运行）
echo.
choice /c 12 /n /m "请输入选项 (1-2): "
if %ERRORLEVEL% equ 1 (
    set "HEADLESS_FLAG="
    set "HEADLESS_DESC=显示窗口（可以看到填写过程）"
) else (
    set "HEADLESS_FLAG=--headless"
    set "HEADLESS_DESC=隐藏窗口（后台运行）"
)

echo.
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.

:: ── 问题 3：确认模式 ─────────────────────────────────────
echo %YELLOW%请选择提交确认模式：%RESET%
echo   %BOLD%[1]%RESET% 保险模式 — 每门课提交前暂停确认（推荐）
echo   %BOLD%[2]%RESET% 全自动模式 — 跳过所有确认，直接提交
echo.
choice /c 12 /n /m "请输入选项 (1-2): "
if %ERRORLEVEL% equ 1 (
    set "CONFIRM_FLAG=--confirm"
    set "CONFIRM_DESC=保险模式（每门课提交前确认）"
) else (
    set "CONFIRM_FLAG=--no-confirm"
    set "CONFIRM_DESC=全自动（跳过所有确认）"
)

echo.
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.

:: ── 问题 4：是否干跑 ─────────────────────────────────────
echo %YELLOW%是否使用干跑模式（只预览选项，不实际填表和提交）？%RESET%
echo   %BOLD%[1]%RESET% 否 — 正式运行（实际填写和提交）
echo   %BOLD%[2]%RESET% 是 — 干跑（只预览，不提交）
echo.
choice /c 12 /n /m "请输入选项 (1-2): "
if %ERRORLEVEL% equ 2 (
    set "DRYRUN_FLAG=--dry-run"
    set "DRYRUN_DESC=干跑（只预览，不提交）"
    set "CONFIRM_FLAG="
    set "CONFIRM_DESC=不适用（干跑模式）"
) else (
    set "DRYRUN_FLAG="
    set "DRYRUN_DESC=正式运行（实际填写和提交）"
)

:: ── 构建情感描述和 flag ──────────────────────────────────
if %SENTIMENT_CHOICE% equ 1 (
    set "SENTIMENT_FLAG=-1"
    set "SENTIMENT_DESC=全部喜欢"
) else if %SENTIMENT_CHOICE% equ 2 (
    set "SENTIMENT_FLAG=-2"
    set "SENTIMENT_DESC=全部一般"
) else if %SENTIMENT_CHOICE% equ 3 (
    set "SENTIMENT_FLAG=-3"
    set "SENTIMENT_DESC=全部讨厌"
) else (
    set "SENTIMENT_FLAG="
    set "SENTIMENT_DESC=每门课单独选择"
)

:: ── 确认摘要 ─────────────────────────────────────────────
echo.
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.
echo %BOLD%╔════════════════════════════════════════════╗%RESET%
echo %BOLD%║            运行配置摘要                     ║%RESET%
echo %BOLD%╠════════════════════════════════════════════╣%RESET%
echo %BOLD%║%RESET% 评价策略 : !SENTIMENT_DESC!
echo %BOLD%║%RESET% 浏览器   : !HEADLESS_DESC!
echo %BOLD%║%RESET% 确认模式 : !CONFIRM_DESC!
echo %BOLD%║%RESET% 运行模式 : !DRYRUN_DESC!
echo %BOLD%╚════════════════════════════════════════════╝%RESET%
echo.

:: 显示等效命令行
set "CMD=python main.py"
if defined SENTIMENT_FLAG set "CMD=!CMD! !SENTIMENT_FLAG!"
if defined HEADLESS_FLAG set "CMD=!CMD! !HEADLESS_FLAG!"
if defined CONFIRM_FLAG set "CMD=!CMD! !CONFIRM_FLAG!"
if defined DRYRUN_FLAG set "CMD=!CMD! !DRYRUN_FLAG!"
echo 💡 等效命令行: %CYAN%!CMD!%RESET%
echo    下次可直接在 cmd 中运行上述命令跳过菜单
echo.
pause

:: ── 执行 ──────────────────────────────────────────────────
echo.
echo %GREEN%%BOLD%^> 正在启动...%RESET%
echo.

python main.py !SENTIMENT_FLAG! !HEADLESS_FLAG! !CONFIRM_FLAG! !DRYRUN_FLAG!
set EXIT_CODE=!ERRORLEVEL!

:: ── 结束 ──────────────────────────────────────────────────
:end_script
echo.
echo ========================================
if %EXIT_CODE% equ 0 (
    echo   %GREEN%√ 脚本执行完成%RESET%
) else (
    echo   %RED%X 脚本异常退出 (exit code: %EXIT_CODE%)%RESET%
)
echo ========================================
pause
exit /b %EXIT_CODE%
