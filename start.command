#!/bin/bash
# ============================================================
# 复旦大学课评自动填写工具 — macOS 启动脚本
# 双击此文件即可运行，首次运行会自动安装依赖
#
# 两种使用方式：
#   1. 双击 → 交互式菜单引导配置
#   2. 终端执行 ./start.command -1 -y → 直接透传参数（专家模式）
# ============================================================
set -e

# 获取脚本所在目录（支持 Finder 双击、Terminal 直接运行）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
VENV_DIR="$SCRIPT_DIR/venv"

# ── 颜色定义 ──────────────────────────────────────────────
BOLD="$(tput bold 2>/dev/null || echo '')"
GREEN="$(tput setaf 2 2>/dev/null || echo '')"
YELLOW="$(tput setaf 3 2>/dev/null || echo '')"
CYAN="$(tput setaf 6 2>/dev/null || echo '')"
RED="$(tput setaf 1 2>/dev/null || echo '')"
RESET="$(tput sgr0 2>/dev/null || echo '')"

# ── 横幅 ──────────────────────────────────────────────────
print_banner() {
    echo ""
    echo "${CYAN}${BOLD}╔════════════════════════════════════════════╗${RESET}"
    echo "${CYAN}${BOLD}║    复旦大学课评自动填写工具                 ║${RESET}"
    echo "${CYAN}${BOLD}║    Course Evaluation Script                ║${RESET}"
    echo "${CYAN}${BOLD}╚════════════════════════════════════════════╝${RESET}"
    echo ""
}

# ── 菜单选择函数 ──────────────────────────────────────────
choose_one() {
    # $1 = 提示文字, $2..$N = 选项
    # 返回选中的序号 (1-based)
    local prompt="$1"
    shift
    local num_options=$#
    local choice=""

    while true; do
        echo "${YELLOW}${prompt}${RESET}"
        local i=1
        for opt in "$@"; do
            echo "  ${BOLD}[$i]${RESET} $opt"
            ((i++))
        done
        echo ""
        read -p "请输入选项 (1-${num_options}): " choice
        if [[ "$choice" =~ ^[0-9]+$ ]] && [ "$choice" -ge 1 ] && [ "$choice" -le "$num_options" ]; then
            return "$choice"
        fi
        echo "${RED}⚠ 无效输入，请输入 1-${num_options}${RESET}"
        echo ""
    done
}

yes_no() {
    # $1 = 提示文字, 默认选项
    # 返回: 1=是, 2=否
    local prompt="$1"
    local choice=""

    while true; do
        echo "${YELLOW}${prompt}${RESET}"
        echo "  ${BOLD}[1]${RESET} 是"
        echo "  ${BOLD}[2]${RESET} 否"
        echo ""
        read -p "请输入选项 (1-2): " choice
        if [ "$choice" = "1" ] || [ "$choice" = "2" ]; then
            return "$choice"
        fi
        echo "${RED}⚠ 无效输入，请输入 1 或 2${RESET}"
        echo ""
    done
}

# ── Python 检测 ──────────────────────────────────────────
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &> /dev/null; then
        major=$("$cmd" -c "import sys; print(sys.version_info.major)" 2>/dev/null)
        minor=$("$cmd" -c "import sys; print(sys.version_info.minor)" 2>/dev/null)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 10 ]; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "${RED}${BOLD}┌─────────────────────────────────────────────┐${RESET}"
    echo "${RED}${BOLD}│  ❌ 未找到 Python 3.10 或更高版本            │${RESET}"
    echo "${RED}${BOLD}│                                             │${RESET}"
    echo "${RED}${BOLD}│  请先安装 Python：                           │${RESET}"
    echo "${RED}${BOLD}│  https://www.python.org/downloads/           │${RESET}"
    echo "${RED}${BOLD}│                                             │${RESET}"
    echo "${RED}${BOLD}│  或通过 Homebrew：                           │${RESET}"
    echo "${RED}${BOLD}│  brew install python@3.12                   │${RESET}"
    echo "${RED}${BOLD}└─────────────────────────────────────────────┘${RESET}"
    echo ""
    read -p "按回车键退出..."
    exit 1
fi

# ── 虚拟环境 ─────────────────────────────────────────────
if [ ! -f "$VENV_DIR/bin/activate" ]; then
    echo ""
    echo "${GREEN}┌─────────────────────────────────────────────┐${RESET}"
    echo "${GREEN}│  🔧 首次运行，正在创建虚拟环境...              │${RESET}"
    echo "${GREEN}│  所有依赖安装在项目文件夹内，不会污染系统       │${RESET}"
    echo "${GREEN}└─────────────────────────────────────────────┘${RESET}"
    echo ""

    $PYTHON -m venv "$VENV_DIR"
    source "$VENV_DIR/bin/activate"

    echo "[INFO] 正在安装 Python 依赖..."
    pip install --upgrade pip --quiet
    pip install -r requirements.txt --quiet
    echo "[INFO] Python 依赖安装完成 ✓"

    echo "[INFO] 正在安装 Playwright 浏览器（可能需要几分钟）..."
    python -m playwright install chromium
    echo "[INFO] Playwright 浏览器安装完成 ✓"

    echo ""
    echo "${GREEN}${BOLD}┌─────────────────────────────────────────────┐${RESET}"
    echo "${GREEN}${BOLD}│  ✅ 环境安装完成！                           │${RESET}"
    echo "${GREEN}${BOLD}└─────────────────────────────────────────────┘${RESET}"
    echo ""
else
    source "$VENV_DIR/bin/activate"
fi

# ── 主流程 ───────────────────────────────────────────────

# 如果有命令行参数，直接透传（专家模式）
if [ $# -gt 0 ]; then
    print_banner
    echo "[INFO] 专家模式：参数透传到 main.py"
    echo "[INFO] 命令行: python main.py $*"
    echo ""
    python main.py "$@"
    EXIT_CODE=$?
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
fi

# ── 交互式菜单模式 ───────────────────────────────────────
print_banner

echo "欢迎使用课评自动填写工具！"
echo "下面将通过几个简单问题配置运行参数。"
echo ""

# ── 问题 1：情感模式 ─────────────────────────────────────
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

choose_one "📝 请选择评价策略（情感模式）：" \
    "全部喜欢 😊  — 以「非常同意」「同意」为主，适合对课程满意的同学" \
    "全部一般 😐  — 以「一般」「中等」为主，适合持中性态度的同学" \
    "全部讨厌 😠  — 以「非常不同意」「不同意」为主，适合对课程不满的同学" \
    "每门课单独选择 — 进入每门课时手动选择喜欢/一般/讨厌/跳过"
SENTIMENT_CHOICE=$?

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── 问题 2：是否显示浏览器 ──────────────────────────────
yes_no "🖥  是否显示浏览器窗口？"
HEADLESS_CHOICE=$?
if [ "$HEADLESS_CHOICE" = "1" ]; then
    HEADLESS_DESC="隐藏窗口（后台运行）"
    HEADLESS_FLAG="--headless"
else
    HEADLESS_DESC="显示窗口（可以看到填写过程）"
    HEADLESS_FLAG=""
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── 问题 3：确认模式 ─────────────────────────────────────
choose_one "🔒 请选择提交确认模式：" \
    "保险模式 🔐 — 每门课提交前暂停确认，可以检查和修改选项（推荐）" \
    "全自动模式 ⚡ — 跳过所有确认，直接提交（适合信任脚本的老用户）"
CONFIRM_CHOICE=$?
if [ "$CONFIRM_CHOICE" = "1" ]; then
    CONFIRM_DESC="保险模式（每门课提交前确认）"
    CONFIRM_FLAG="--confirm"
else
    CONFIRM_DESC="全自动（跳过所有确认）"
    CONFIRM_FLAG="--no-confirm"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── 问题 4：是否干跑 ─────────────────────────────────────
yes_no "🧪 是否使用干跑模式（只预览选项，不实际填表和提交）？"
DRYRUN_CHOICE=$?
if [ "$DRYRUN_CHOICE" = "1" ]; then
    DRYRUN_DESC="干跑（只预览，不提交）"
    DRYRUN_FLAG="--dry-run"
    # 干跑模式下确认无关紧要，但保持一致
    CONFIRM_FLAG=""
    CONFIRM_DESC="不适用（干跑模式）"
else
    DRYRUN_DESC="正式运行（实际填写和提交）"
    DRYRUN_FLAG=""
fi

# ── 构建 CLI 参数 ────────────────────────────────────────
case $SENTIMENT_CHOICE in
    1) SENTIMENT_FLAG="-1"; SENTIMENT_DESC="全部喜欢 😊" ;;
    2) SENTIMENT_FLAG="-2"; SENTIMENT_DESC="全部一般 😐" ;;
    3) SENTIMENT_FLAG="-3"; SENTIMENT_DESC="全部讨厌 😠" ;;
    4) SENTIMENT_FLAG="";    SENTIMENT_DESC="每门课单独选择 🔄" ;;
esac

# ── 确认摘要 ─────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "${BOLD}╔════════════════════════════════════════════╗${RESET}"
echo "${BOLD}║            运行配置摘要                     ║${RESET}"
echo "${BOLD}╠════════════════════════════════════════════╣${RESET}"
printf "${BOLD}║${RESET} 评价策略 : %-32s ${BOLD}║${RESET}\n" "$SENTIMENT_DESC"
printf "${BOLD}║${RESET} 浏览器   : %-32s ${BOLD}║${RESET}\n" "$HEADLESS_DESC"
printf "${BOLD}║${RESET} 确认模式 : %-32s ${BOLD}║${RESET}\n" "$CONFIRM_DESC"
printf "${BOLD}║${RESET} 运行模式 : %-32s ${BOLD}║${RESET}\n" "$DRYRUN_DESC"
echo "${BOLD}╚════════════════════════════════════════════╝${RESET}"
echo ""

# 显示等效命令行（帮助用户学习 CLI 用法）
CMD="python main.py"
[ -n "$SENTIMENT_FLAG" ] && CMD="$CMD $SENTIMENT_FLAG"
[ -n "$HEADLESS_FLAG" ] && CMD="$CMD $HEADLESS_FLAG"
[ -n "$CONFIRM_FLAG" ] && CMD="$CMD $CONFIRM_FLAG"
[ -n "$DRYRUN_FLAG" ] && CMD="$CMD $DRYRUN_FLAG"
echo "💡 等效命令行: ${CYAN}$CMD${RESET}"
echo "   下次可直接在终端运行上述命令跳过菜单"
echo ""

read -p "按回车键开始运行（Ctrl+C 取消）..."

# ── 执行 ──────────────────────────────────────────────────
echo ""
echo "${GREEN}${BOLD}▶ 正在启动...${RESET}"
echo ""

python main.py $SENTIMENT_FLAG $HEADLESS_FLAG $CONFIRM_FLAG $DRYRUN_FLAG
EXIT_CODE=$?

# ── 结束 ──────────────────────────────────────────────────
echo ""
echo "========================================"
if [ $EXIT_CODE -eq 0 ]; then
    echo "  ${GREEN}✅ 脚本执行完成${RESET}"
else
    echo "  ${RED}❌ 脚本异常退出 (exit code: $EXIT_CODE)${RESET}"
fi
echo "========================================"
read -p "按回车键关闭窗口..."
exit $EXIT_CODE
