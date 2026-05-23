# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project: 课评自动填写脚本 (Course Evaluation Auto-Fill Script)

Automate completion of university course evaluations via browser automation. The evaluation form is all multiple-choice questions with some requiring additional text input.

## Core Requirements

- **Sentiment preset per course**: Before evaluating each course, user picks `喜欢` / `一般` / `讨厌`, which drives answer selection strategy.
- **喜欢 (Like)**: Majority positive answers, some neutral, **no negative**.
- **一般 (Neutral)**: Majority neutral answers, at most **one** negative.
- **讨厌 (Dislike)**: Majority negative answers, some neutral.
- **Scoring direction**: One question is reverse-scored (反向评分), all others are forward-scored (正向评分). The script must handle this correctly per the chosen sentiment.
- **Yes/No questions**: Some questions are boolean yes/no type.
- **Text-fill questions**: Some options require additional text content, filled from presets.

## Planned Architecture

- **Language**: Python (recommended for browser automation + ease of config)
- **Browser automation**: Playwright (via `playwright` Python package)
- **Config file**: YAML/JSON per term defining courses, question templates, text presets, and scoring rules.
- **Execution flow**:
  1. Load course list and question definitions from config.
  2. For each course, prompt user for sentiment (喜欢/一般/讨厌).
  3. Based on sentiment + question type (forward/reverse/bool), auto-select appropriate options.
  4. Fill any required text fields from preset templates.
  5. Submit and proceed to next course.

## Key Design Decisions (to be made)

- Whether to use Playwright or a simpler HTTP request-based approach (if the evaluation API can be reverse-engineered).
- Config format: YAML vs JSON vs Python dataclasses.
- Whether to run fully headless or show the browser for user verification.

## Development Commands

```bash
# Install dependencies
pip install playwright
playwright install chromium

# Run the script
python main.py
```
