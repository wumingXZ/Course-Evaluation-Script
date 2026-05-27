# 课评自动填写脚本

复旦大学课程评估自动化工具，基于 Playwright 浏览器自动化。

## 安装

```bash
git clone https://github.com/wumingXZ/Course-Evaluation-Script.git
cd Course-Evaluation-Script
pip install -r requirements.txt
playwright install chromium
```

> 依赖包（`requirements.txt`）：playwright（浏览器自动化）、pydantic（配置校验）、pyyaml（YAML 解析）。Python 版本要求 ≥ 3.10。

### 首次登录

首次运行 `python main.py` 会打开浏览器窗口，手动完成 SSO 登录后关闭即可。登录态自动保存到 `data/storage_state.json`，后续无需再次登录。

## 配置

编辑 `config/term.yaml`，**只需改一个字段**：

```yaml
semester: "2025-2026-2"    # ← 改成当前学期
```

> 学期格式：`学年-学年-学期`。春季学期为 `2`，秋季为 `1`。例如 2026 年春季学期写 `2025-2026-2`。

如果学校教务系统 URL 变了，修改以下两行（一般不需要改）：

```yaml
app_base_url: "https://ce.fudan.edu.cn/index.html?v=3.41.0"
evaluation_route: "#/my-task/details/UnFinished/0/1/Final/undefined/4"
```

## 使用

```bash
# 交互模式：每门课手动确认
python main.py

# 全部喜欢，自动提交
python main.py -1 -y

# 全部一般，干跑预览不提交
python main.py -2 --dry-run

# 全部讨厌，无头模式全自动
python main.py -3 -y --headless

# 仅指定学期
python main.py --semester 2026-2027-1
```

## 命令行参数

| 参数 | 作用 |
|------|------|
| `-1` | 全部课程用**喜欢**（非常同意为主，无负面，一般 ≤ 2 题） |
| `-2` | 全部课程用**一般**（中性为主，最多 1 题负面） |
| `-3` | 全部课程用**讨厌**（负面为主） |
| `-y` | 跳过确认，自动提交 |
| `--dry-run` | 只打印选项，不填表不提交 |
| `--headless` | 不显示浏览器窗口 |
| `--verbose`, `-v` | 显示详细日志（DOM 结构、每题选项） |
| `--semester`, `-s` | 临时覆盖学期（如 `2026-2027-1`） |
| `--config`, `-c` | 指定配置文件（默认 `term.yaml`） |

不加 `-1/-2/-3` 时，每门课会交互式询问情感。

## 题目类型与固定规则

脚本自动检测页面上 18 道题，分 3 类：

| 索引 | 类型 | 说明 |
|------|------|------|
| 0-14 | 单选 5 级 | Likert 量表：非常不同意 → 非常同意 |
| 15 | 单选 3 级 | 是否推荐：强烈不推荐 / 一般 / 强烈推荐 |
| 16-17 | 多选 checkbox | 课程收获等方面，勾选「无」 |

以下题目有**固定规则**（不随情感变化）：

| 题目 | 规则 | 原因 |
|------|------|------|
| Q1（第2题） | 固定「约等于」 | 课后学习时间，选中间值 |
| Q12（第13题） | 固定「非常不同意」 | 反向评分题 |
| Q15（推荐题） | 一般/讨厌时固定「一般」 | 避免触发理由弹窗 |
| Q16-Q17（多选） | 固定只选「无」 | 不需要勾选具体方面 |

> 如需修改这些规则，编辑 `src/answer_engine.py` 中 `FIXED_*` 常量。

## 多教师课程

部分课程有多位授课教师（如军事理论、强国之路），脚本会自动：

1. 检测页面上的教师标签页（Tab）
2. 依次切换到每位教师
3. 弹出「套用前一位老师评价」时自动点击确认
4. 每位教师用同一情感策略
5. 全部完成后一次性提交

## 情感策略详情

### 喜欢
- 权重分布：非常同意 50%、同意 40%、一般 10%、负面 0%
- 一般选项硬限制 ≤ 2 题
- 推荐题：按权重倾向于「强烈推荐」
- 文本输入：自动用预设模板填充

### 一般
- 权重分布：一般 70%、同意 10%、不同意 10%、非常不同意 5%、非常同意 5%
- 负面硬限制 ≤ 1 题
- 推荐题：固定「一般」
- 文本输入：检测到时暂停，手动输入理由

### 讨厌
- 权重分布：非常不同意 60%、不同意 30%、一般 10%、正面 0%
- 推荐题：固定「一般」
- 文本输入：检测到时暂停，手动输入理由

### 权重配置

编辑 `config/presets.yaml` 可自定义权重：

```yaml
distributions:
  forward:
    like:
      weights: [0.0, 0.0, 0.1, 0.4, 0.5]  # 索引 0=最差, 4=最好
```

## 项目结构

```
├── main.py                  # 入口：命令行解析 + 主流程
├── config/
│   ├── term.yaml            # 学期、课程覆盖、文本预设
│   └── presets.yaml         # 情感→选项权重分布
├── src/
│   ├── browser_manager.py   # 浏览器启动/关闭，弹窗自动 dismiss
│   ├── authenticator.py     # 登录态检测与恢复
│   ├── page_navigator.py    # 页面导航：课程列表、进入评价、Tab 切换、
│   │                        #   弹窗关闭、理由输入
│   ├── question_detector.py # 题目扫描：radio 分组、checkbox 检测
│   ├── dom_utils.py         # DOM 提取：JS 端分组、标签提取、归一化
│   ├── answer_engine.py     # 选项生成：权重随机 + 固定规则 + 约束
│   ├── form_filler.py       # 表单填写：radio/checkbox + 文本输入
│   ├── reviewer.py          # 交互式审核：确认 / 修改 / 跳过
│   ├── config_loader.py     # YAML 配置加载
│   ├── cli.py               # 终端 UI：进度条、情感提示
│   └── models.py            # Pydantic 数据模型
└── data/
    ├── storage_state.json   # 浏览器登录态缓存（自动生成）
    └── screenshots/         # 提交前截图
```

## 执行流程

```
启动浏览器 → 恢复登录态 → 提取课程列表
    │
    └→ 每门课：
        选择情感 → 进入评价页 → 关闭弹窗 → 检测教师 Tab
            │
            └→ 每位教师：
                切换 Tab → 套用评价 → 检测题目 → 生成选项
                → [审核确认] → 填写表单
            │
        提交评价 → [填写理由] → 下一门课
```

## 自定义课程覆盖

在 `config/term.yaml` 的 `courses` 字段可按题目标题覆盖自动检测：

```yaml
courses:
  - name: "高等数学A"
    overrides:
      "教师教学态度":        # 题目标题（需页面能提取到）
        type: "reverse"      # 覆盖题型：forward / reverse / yesno
        force: "positive"    # 强制选最高分
      "多余的题目":
        skip: true           # 跳过此题
```

> 注意：当前版本题目标题提取不稳定，overrides 功能可能无法生效。建议使用 `src/answer_engine.py` 中的 `FIXED_*` 常量来配置固定规则。

## 注意事项

- 建议先用 `--dry-run` 预览，确认无误再正式运行
- 正式运行保留默认的 `--confirm` 模式（保险模式），提交前可检查修改
- 页面结构变化时可能需要调整 `config/term.yaml` 中的选择器
- 文本预设模板在 `config/term.yaml` 的 `text_presets` 字段，可按需修改

## 贡献 / 二次开发

```bash
# 1. Fork 本仓库（GitHub 页面右上角 Fork 按钮）

# 2. 克隆你自己的 fork
git clone https://github.com/你的用户名/Course-Evaluation-Script.git
cd Course-Evaluation-Script

# 3. 安装依赖
pip install -r requirements.txt
playwright install chromium

# 4. 创建功能分支
git checkout -b feat/my-feature

# 5. 修改代码后提交
git add .
git commit -m "feat: 添加某个功能"

# 6. 推送到自己的 fork
git push origin feat/my-feature

# 7. 在 GitHub 上发起 Pull Request
```

