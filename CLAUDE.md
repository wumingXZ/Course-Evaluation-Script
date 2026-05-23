# CLAUDE.md

复旦大学课程评估自动化脚本。Playwright 浏览器自动化，批量填写课评表单。

## 技术栈

- Python 3.10+, Playwright (sync API), Pydantic v2, PyYAML
- 不依赖 AI/LLM 模块，纯规则引擎驱动选项生成

## 常用命令

```bash
python main.py              # 交互模式，逐门确认
python main.py -1 -y        # 全喜欢，自动提交
python main.py -2 --dry-run # 全一般，干跑预览
python main.py -1 -y --headless  # 无头全自动
python main.py -v           # 详细日志（显示每题选项和 DOM 信息）
python main.py --semester 2026-2027-1  # 指定学期
```

## 架构

```
main.py                     # CLI 入口 + 编排主流程
config/
  term.yaml                 # 学期、URL、选择器、行为、文本预设模板
  presets.yaml              # 情感 → 选项权重分布（通常不改）
src/
  models.py                 # Pydantic 数据模型（Sentiment, Question, Selection 等）
  config_loader.py          # YAML → Pydantic 模型
  browser_manager.py        # Playwright 浏览器生命周期 + 存储状态
  authenticator.py          # SSO 登录检测与恢复
  page_navigator.py         # 课程列表提取、进入评价、Tab 切换、提交、弹窗处理
  question_detector.py      # 题目扫描入口：调度 radio/checkbox 检测，题型判定
  dom_utils.py              # 核心 DOM 分析（单次 page.evaluate 分组 radio、提取标题/选项）
  answer_engine.py          # 权重随机 + 固定规则 + 约束 → 生成 Selection 列表
  form_filler.py            # 填写 radio/checkbox + 关联的文本输入框
  reviewer.py               # 交互式审核：确认/修改/跳过
  cli.py                    # 终端 UI（进度条、情感提示、横幅、摘要）
data/
  storage_state.json        # 浏览器登录态缓存（自动保存）
  screenshots/              # 提交前截图
```

## 固定规则（answer_engine.py）

以下规则不随情感变化，适用于所有课程：

| 题号 | 规则 | 原因 |
|------|------|------|
| Q1 (index=1) | 固定选项 index=2（约等于） | 课后学习时间选中间值 |
| Q12 (index=12) | 固定 index=0（非常不同意），强制 REVERSE 类型 | 反向评分题 |
| Q15 (index=15) | neutral/dislike 时固定 index=1（一般） | 避免极端推荐触发理由弹窗 |
| Q16, Q17 | 固定只选「无」选项 | checkbox 题不需要勾选具体方面 |

修改这些规则只需改 `answer_engine.py` 中的 `FIXED_OPTIONS`、`FIXED_REVERSE_INDEX` 等字典常量。

## 题目检测（question_detector.py + dom_utils.py）

`extract_all_questions()` 在单次 `page.evaluate()` 中完成全部 DOM 分析：

1. **分组 radio**：优先按 HTML name 属性，其次按结构容器（form-item），最后按 value 序列趋势反转检测边界
2. **提取标题**：沿 DOM 树向上搜索兄弟元素文本，多策略回退
3. **归一化选项顺序**：如果页面 render 顺序是「非常同意→非常不同意」，自动 reverse 使 index=0 始终 = 最差，记录 `was_reversed` 标记
4. **题型判定**：2 选项 + 是/否标签 → yesno；含「反向」关键词 → reverse；其余 → forward
5. **checkbox 题**：单独提取，按 form-item 容器分组

`fill_form()` 在填写时会用 `was_reversed` 映射回页面原始顺序。

## 文本填写

`term.yaml` 的 `text_presets` 按情感提供预设文本模板。`presets.yaml` 的 `textfill` 控制触发概率。neutral/dislike 模式下，低分选项触发的理由输入框会暂停让用户手动填写。

## 多教师课程

`detect_teacher_tabs()` 检测 Ant Design / Element UI 的 Tab 组件，依次切换每位教师，套用前一教师评价，最后一次性提交。

## 认证

首次运行打开浏览器等待手动 SSO 登录。登录态自动保存到 `data/storage_state.json`，后续运行自动恢复。`_is_login_page()` 同时检查 URL 域名和页面内容（密码框 + 登录关键词）。
