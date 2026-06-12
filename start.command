#!/bin/bash
# ============================================================
# 复旦大学课评自动填写工具 — macOS 启动脚本
# 双击此文件即可运行，首次运行会自动安装依赖
# ============================================================
set -e

# 获取脚本所在目录（支持 Finder 双击、Terminal 直接运行）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
VENV_DIR="$SCRIPT_DIR/venv"

echo "========================================"
echo "  复旦大学课评自动填写工具"
echo "  Course Evaluation Script"
echo "========================================"
echo ""

# ── Python 检测 ──────────────────────────────────────────
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &> /dev/null; then
        # 检查版本 >= 3.10
        ver=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
        major=$("$cmd" -c "import sys; print(sys.version_info.major)" 2>/dev/null)
        minor=$("$cmd" -c "import sys; print(sys.version_info.minor)" 2>/dev/null)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 10 ]; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "┌─────────────────────────────────────────────┐"
    echo "│  ❌ 未找到 Python 3.10 或更高版本            │"
    echo "│                                             │"
    echo "│  请先安装 Python：                           │"
    echo "│  https://www.python.org/downloads/           │"
    echo "│                                             │"
    echo "│  或通过 Homebrew：                           │"
    echo "│  brew install python@3.12                   │"
    echo "└─────────────────────────────────────────────┘"
    echo ""
    read -p "按回车键退出..."
    exit 1
fi

echo "[INFO] 使用 Python: $PYTHON ($($PYTHON --version))"

# ── 虚拟环境 ─────────────────────────────────────────────
if [ ! -f "$VENV_DIR/bin/activate" ]; then
    echo ""
    echo "┌─────────────────────────────────────────────┐"
    echo "│  🔧 首次运行，正在创建虚拟环境...              │"
    echo "│  所有依赖安装在项目文件夹内，不会污染系统       │"
    echo "└─────────────────────────────────────────────┘"
    echo ""

    $PYTHON -m venv "$VENV_DIR"

    # 激活虚拟环境
    source "$VENV_DIR/bin/activate"

    echo "[INFO] 正在安装 Python 依赖..."
    pip install --upgrade pip --quiet
    pip install -r requirements.txt --quiet
    echo "[INFO] Python 依赖安装完成 ✓"

    echo "[INFO] 正在安装 Playwright 浏览器（可能需要几分钟）..."
    python -m playwright install chromium
    echo "[INFO] Playwright 浏览器安装完成 ✓"

    echo ""
    echo "┌─────────────────────────────────────────────┐"
    echo "│  ✅ 环境安装完成！                           │"
    echo "└─────────────────────────────────────────────┘"
    echo ""
else
    # 激活已有的虚拟环境
    source "$VENV_DIR/bin/activate"
    echo "[INFO] 使用已有虚拟环境"
fi

# ── 运行主程序 ───────────────────────────────────────────
echo ""
echo "[INFO] 启动课评脚本..."
echo "  提示：使用 -1 -y 参数可直接全自动运行"
echo "  用法：在 Terminal 中执行 ./start.command -1 -y --headless"
echo ""

python main.py "$@"
EXIT_CODE=$?

# ── 保持终端打开 ─────────────────────────────────────────
echo ""
echo "========================================"
if [ $EXIT_CODE -eq 0 ]; then
    echo "  脚本执行完成"
else
    echo "  脚本异常退出 (exit code: $EXIT_CODE)"
fi
echo "========================================"
read -p "按回车键关闭窗口..."
exit $EXIT_CODE
