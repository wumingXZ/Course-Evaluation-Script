# 课评自动填写脚本

复旦大学课程评估自动化工具。基于 Playwright 浏览器自动化，支持单选/多选/推荐题，多教师课程，一键批量填写。

## 快速开始

```bash
# 安装依赖
pip install playwright
playwright install chromium

# 配置学期（修改 config/term.yaml 中的 semester 字段）

# 首次运行（交互模式，每门课确认后提交）
python main.py

# 全自动批量：所有课程「喜欢」，跳过确认
python main.py -1 -y

# 所有课程「一般」，干跑预览不提交
python main.py -2 --dry-run

# 所有课程「讨厌」，无头模式全自动
python main.py -3 -y --headless
```

## CLI 参数

| 参数 | 说明 |
|------|------|
| `-1` | 全部课程使用 **喜欢** 情感（正面为主，无负面） |
| `-2` | 全部课程使用 **一般** 情感（中性为主，最多 1 题负面） |
| `-3` | 全部课程使用 **讨厌** 情感（负面为主） |
| `-y` | 跳过确认，自动提交 |
| `--dry-run` | 干跑模式：打印选择但不填表、不提交 |
| `--headless` | 无头模式（不显示浏览器窗口） |
| `--verbose`, `-v` | 详细日志，显示 DOM 结构和每题选项 |
| `--semester`, `-s` | 覆盖学期（如 `2026-2027-1`） |
| `--ai` | 启用 AI 模块生成个性化文本 |
| `--config`, `-c` | 指定配置文件（默认 `term.yaml`） |

## 情感策略

### 喜欢（Like）
- 正向评分题：非常同意 50%、同意 40%、一般 10%，**无负面**
- 一般选项 ≤ 2 题
- 推荐题：倾向于「强烈推荐」

### 一般（Neutral）
- 正向评分题：一般 70%，**最多 1 题负面**
- 推荐题：固定「一般」
- 触发低分理由弹窗时暂停，等待手动输入

### 讨厌（Dislike）
- 正向评分题：非常不同意 60%、不同意 30%、一般 10%
- 推荐题：固定「一般」
- 触发低分理由弹窗时暂停，等待手动输入

## 题目类型

脚本自动检测 3 种题型：

| 类型 | 检测方式 | 选项 |
|------|----------|------|
| **单选（radio）** | 5 级 Likert 量表 | 非常不同意 → 非常同意 |
| **推荐（radio）** | 含"推荐"关键词 | 强烈不推荐 / 一般 / 强烈推荐 |
| **多选（checkbox）** | form-item 容器内 | 实践技能、师德师风等 |

### 固定规则（全局生效）

| 题目 | 规则 |
|------|------|
| Q1（课后学习时间） | 固定选「约等于」 |
| Q12（反向评分题） | 固定选「非常不同意」 |
| Q15（推荐题） | 一般/讨厌时固定「一般」 |
| Q16-Q17（多选） | 固定只选「无」 |

> Q12/Q15/Q16/Q17 的索引硬编码在 `src/answer_engine.py:34-37`，如需调整请修改 `FIXED_*` 常量。

## 配置文件

### config/term.yaml — 学期配置

```yaml
semester: "2025-2026-2"     # 每学期修改此处
app_base_url: "https://ce.fudan.edu.cn/index.html?v=3.41.0"
evaluation_route: "#/my-task/details/UnFinished/0/1/Final/undefined/4"

behavior:
  confirm_before_submit: true  # 默认保险模式

# 课程级自定义覆盖（按题目标题匹配，可选）
courses:
  - name: "高等数学A"
    overrides:
      "教师教学态度":
        type: "reverse"       # 覆盖自动检测：forward/reverse/yesno
        force: "positive"     # 强制选最高分
      "不必要的题目":
        skip: true            # 跳过此题

text_presets:                 # 无 AI 时的文本填充模板
  like:
    - "老师教学认真负责，讲解清晰，受益匪浅。"
  neutral:
    - "课程内容中规中矩，教学方式可以更丰富一些。"
  dislike:
    - "教学方式有待改进，课堂互动较少。"
```

### config/presets.yaml — 权重分布

```yaml
distributions:
  forward:          # 正向评分 Likert 5
    like:    { weights: [0.0, 0.0, 0.1, 0.4, 0.5] }
    neutral: { weights: [0.05, 0.1, 0.7, 0.1, 0.05] }
    dislike: { weights: [0.3, 0.5, 0.2, 0.0, 0.0] }
  textfill:         # 文本填写触发率
    like: 0.3
    neutral: 0.6
    dislike: 0.3
```

权重索引：0 = 最差（非常不同意），4 = 最好（非常同意）。

## 项目架构

```
├── main.py                     # 入口：CLI 解析、主流程编排
├── config/
│   ├── term.yaml               # 学期配置（课程、选择器、文本预设）
│   └── presets.yaml            # 情感→选项权重分布
├── src/
│   ├── browser_manager.py      # Playwright 浏览器生命周期 + 弹窗自动 dismiss
│   ├── authenticator.py        # 登录态检查与恢复
│   ├── page_navigator.py       # 页面导航（课程列表提取、评价进入、tab切换、
│   │                           #   弹窗关闭、理由弹窗处理）
│   ├── question_detector.py    # 题目扫描（radio 分组 + checkbox 检测）
│   ├── dom_utils.py            # DOM 提取核心（JS 端分组、标签提取、归一化）
│   ├── answer_engine.py        # 选项生成（权重随机 + 固定规则 + 约束）
│   ├── form_filler.py          # 表单填写（radio/checkbox + 文本输入 + 索引映射）
│   ├── reviewer.py             # 交互式审核（确认/修改/跳过）
│   ├── config_loader.py        # YAML 配置加载
│   ├── cli.py                  # 终端 UI（banner、进度条、情感提示）
│   ├── models.py               # Pydantic 数据模型
│   └── ai/                     # AI 文本生成模块（可选）
│       ├── base.py
│       ├── claude_provider.py
│       ├── openai_provider.py
│       └── writer.py
└── data/
    ├── storage_state.json      # 浏览器登录态缓存
    └── screenshots/            # 截图保存
```

## 执行流程

```
启动浏览器 → 检查登录态 → 提取课程列表
    ↓
对每门课：
    选择情感 → 进入评价页 → 关闭弹窗 → 检测教师 tab
        ↓
    对每位教师：
        切换 tab → 套用前一位评价 → 检测题目 → 生成选项
        → [审核] → 填写表单 → 截图
        ↓
    提交评价 → [填写理由弹窗] → 返回课程列表
```

## 多教师课程

部分课程（如"军事理论"、"强国之路"）有多位授课教师。脚本自动：

1. 检测 Ant Design / Element UI 标签页
2. 依次切换到每位教师的评价 sheet
3. 切换后自动点击「使用前一位老师的评价」套用
4. 每位教师使用相同的情感策略
5. 全部完成后一次性提交

## 选项映射机制

页面上的 radio 原始顺序为 `非常同意 → 非常不同意`（best→worst）。JS 端检测时归一化为 `非常不同意 → 非常同意`（worst→best），使索引 0 = 最差、索引 N-1 = 最好。填写时通过 `was_reversed` 标志将归一化索引映射回原始 DOM 位置：

```
raw_idx = (n_options - 1) - normalized_idx
```

这保证了无论页面 DOM 顺序如何，填充时都能点击正确的选项。

## 表单填写时文本输入处理

- **喜欢模式**：自动用预设文本填充
- **一般/讨厌模式**：检测到文本输入框时暂停，等待手动输入理由
- **提交后弹窗**：自动检测评分理由弹窗，暂停等待手动填写

## 注意事项

- 首次运行需要手动登录，登录态会缓存到 `data/storage_state.json`
- 建议先用 `--dry-run` 预览选择是否正确
- 正式运行建议保留默认的 `--confirm` 模式（保险模式）
- 目标页面结构变化时可能需要调整 `config/term.yaml` 中的选择器
