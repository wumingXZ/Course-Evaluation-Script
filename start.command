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

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
VENV_DIR="$SCRIPT_DIR/venv"

# ── 终端样式 ──────────────────────────────────────────────
BOLD="$(tput bold 2>/dev/null || echo '')"
GREEN="$(tput setaf 2 2>/dev/null || echo '')"
YELLOW="$(tput setaf 3 2>/dev/null || echo '')"
CYAN="$(tput setaf 6 2>/dev/null || echo '')"
RED="$(tput setaf 1 2>/dev/null || echo '')"
RESET="$(tput sgr0 2>/dev/null || echo '')"

banner() {
    echo ""
    echo "${CYAN}${BOLD}╔════════════════════════════════════════════╗${RESET}"
    echo "${CYAN}${BOLD}║    复旦大学课评自动填写工具                 ║${RESET}"
    echo "${CYAN}${BOLD}║    Course Evaluation Script                ║${RESET}"
    echo "${CYAN}${BOLD}╚════════════════════════════════════════════╝${RESET}"
    echo ""
}

# ── 交互函数：输出到 stdout，用 $(...) 捕获 ──────────────────
choose_one() {
    # 用法: choice=$(choose_one "提示" "选项1" "选项2" ...)
    # 输出选中序号 (1-based) 到 stdout
    local prompt="$1"; shift; local n=$#
    while true; do
        echo "${YELLOW}${prompt}${RESET}" >&2
        local i=1
        for opt in "$@"; do echo "  ${BOLD}[$i]${RESET} $opt" >&2; ((i++)); done
        echo "" >&2
        read -p "请输入选项 (1-${n}): " choice
        if [[ "$choice" =~ ^[0-9]+$ ]] && [ "$choice" -ge 1 ] && [ "$choice" -le "$n" ]; then
            echo "$choice"
            return 0
        fi
        echo "${RED}⚠ 无效输入，请输入 1-${n}${RESET}" >&2
        echo "" >&2
    done
}

yes_no() {
    # 用法: yn=$(yes_no "提示")
    # 输出 "y" 或 "n" 到 stdout
    local prompt="$1"
    while true; do
        echo "${YELLOW}${prompt}${RESET}" >&2
        echo "  ${BOLD}[1]${RESET} 是" >&2
        echo "  ${BOLD}[2]${RESET} 否" >&2
        echo "" >&2
        read -p "请输入选项 (1-2): " choice
        case "$choice" in
            1) echo "y"; return 0 ;;
            2) echo "n"; return 0 ;;
        esac
        echo "${RED}⚠ 无效输入，请输入 1 或 2${RESET}" >&2
        echo "" >&2
    done
}

# ── Python 检测 ──────────────────────────────────────────
find_python() {
    for cmd in python3 python; do
        if command -v "$cmd" &> /dev/null; then
            major=$("$cmd" -c "import sys; print(sys.version_info.major)" 2>/dev/null) || continue
            minor=$("$cmd" -c "import sys; print(sys.version_info.minor)" 2>/dev/null) || continue
            if [ "$major" -ge 3 ] && [ "$minor" -ge 10 ]; then
                echo "$cmd"
                return 0
            fi
        fi
    done
    return 1
}

PYTHON=$(find_python) || {
    echo "${RED}${BOLD}┌─────────────────────────────────────────────┐${RESET}"
    echo "${RED}${BOLD}│  ❌ 未找到 Python 3.10 或更高版本            │${RESET}"
    echo "${RED}${BOLD}│  安装: https://www.python.org/downloads/     │${RESET}"
    echo "${RED}${BOLD}│  或: brew install python@3.12               │${RESET}"
    echo "${RED}${BOLD}└─────────────────────────────────────────────┘${RESET}"
    echo ""; read -p "按回车键退出..."; exit 1
}

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
    echo "[INFO] ✅ Python 依赖安装完成"
    echo "[INFO] 正在安装 Playwright 浏览器（可能需要几分钟）..."
    python -m playwright install chromium
    echo ""
    echo "${GREEN}${BOLD}┌─────────────────────────────────────────────┐${RESET}"
    echo "${GREEN}${BOLD}│  ✅ 环境安装完成！                           │${RESET}"
    echo "${GREEN}${BOLD}└─────────────────────────────────────────────┘${RESET}"
    echo ""
else
    source "$VENV_DIR/bin/activate"
fi

# ── 主流程 ───────────────────────────────────────────────

# 有命令行参数 → 专家模式，直接透传
if [ $# -gt 0 ]; then
    banner
    echo "[INFO] 专家模式：参数透传到 main.py"
    echo ""
    set +e; python main.py "$@"; exit_code=$?; set -e
    echo ""; echo "========================================"
    [ $exit_code -eq 0 ] && echo "  ✅ 脚本执行完成" || echo "  ❌ 脚本异常退出 (exit code: $exit_code)"
    echo "========================================"
    read -p "按回车键关闭窗口..."
    exit $exit_code
fi

# ── 交互式菜单 ───────────────────────────────────────────
banner
echo "${YELLOW}⚠️  免责声明：本项目仅用于学习用途，使用者自行承担一切后果。${RESET}"
echo ""
echo "欢迎使用课评自动填写工具！下面通过几个问题配置运行参数。"
echo ""

# Q1: 情感模式
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
sentiment=$(choose_one "📝 请选择评价策略（情感模式）：" \
    "全部喜欢 😊  — 以「非常同意」「同意」为主，适合对课程满意的同学" \
    "全部一般 😐  — 以「一般」「中等」为主，适合持中性态度的同学" \
    "全部讨厌 😠  — 以「非常不同意」「不同意」为主，适合对课程不满的同学" \
    "每门课单独选择 — 进入每门课时手动选择喜欢/一般/讨厌/跳过")

echo ""; echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"; echo ""

# Q2: 浏览器
headless=$(yes_no "🖥  是否隐藏浏览器窗口（后台运行）？")

echo ""; echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"; echo ""

# Q3: 确认模式
confirm=$(choose_one "🔒 请选择提交确认模式：" \
    "保险模式 🔐 — 每门课提交前暂停确认，可以检查和修改选项（推荐）" \
    "全自动模式 ⚡ — 跳过所有确认，直接提交")

echo ""; echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"; echo ""

# Q4: 干跑
dryrun=$(yes_no "🧪 是否使用干跑模式（只预览选项，不实际填表和提交）？")

# ── 翻译为 CLI flag ──────────────────────────────────────
case $sentiment in
    1) s_flag="-1";      s_desc="全部喜欢 😊" ;;
    2) s_flag="-2";      s_desc="全部一般 😐" ;;
    3) s_flag="-3";      s_desc="全部讨厌 😠" ;;
    4) s_flag="";        s_desc="每门课单独选择 🔄" ;;
esac

[ "$headless" = "y" ] && h_flag="--headless" && h_desc="隐藏窗口" || { h_flag=""; h_desc="显示窗口"; }
[ "$confirm" = "1" ]   && c_flag="--confirm" && c_desc="保险模式（逐门确认）" || { c_flag="--no-confirm"; c_desc="全自动（跳过确认）"; }

if [ "$dryrun" = "y" ]; then
    d_flag="--dry-run"; d_desc="干跑（只预览）"
    c_flag=""; c_desc="不适用（干跑模式）"
else
    d_flag=""; d_desc="正式运行"
fi

# ── 摘要 ─────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "${BOLD}╔════════════════════════════════════════════╗${RESET}"
echo "${BOLD}║            运行配置摘要                     ║${RESET}"
echo "${BOLD}╠════════════════════════════════════════════╣${RESET}"
printf "${BOLD}║${RESET} 评价策略 : %-32s ${BOLD}║${RESET}\n" "$s_desc"
printf "${BOLD}║${RESET} 浏览器   : %-32s ${BOLD}║${RESET}\n" "$h_desc"
printf "${BOLD}║${RESET} 确认模式 : %-32s ${BOLD}║${RESET}\n" "$c_desc"
printf "${BOLD}║${RESET} 运行模式 : %-32s ${BOLD}║${RESET}\n" "$d_desc"
echo "${BOLD}╚════════════════════════════════════════════╝${RESET}"
echo ""

cmd="python main.py${s_flag:+ $s_flag}${h_flag:+ $h_flag}${c_flag:+ $c_flag}${d_flag:+ $d_flag}"
echo "💡 等效命令行: ${CYAN}${cmd}${RESET}"
echo "   下次可直接在终端运行 ./start.command${s_flag:+ $s_flag}${h_flag:+ $h_flag}${c_flag:+ $c_flag}${d_flag:+ $d_flag}"
echo ""

read -p "按回车键开始运行（Ctrl+C 取消）..."

# ── 执行 ──────────────────────────────────────────────────
echo ""; echo "${GREEN}${BOLD}▶ 正在启动...${RESET}"; echo ""
set +e  # 允许 main.py 以非零退出（用户中断等）
python main.py $s_flag $h_flag $c_flag $d_flag
exit_code=$?
set -e

echo ""; echo "========================================"
[ $exit_code -eq 0 ] && echo "  ${GREEN}✅ 脚本执行完成${RESET}" || echo "  ${RED}❌ 脚本异常退出 (exit code: $exit_code)${RESET}"
echo "========================================"
read -p "按回车键关闭窗口..."
exit $exit_code
