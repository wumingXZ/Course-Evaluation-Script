#!/usr/bin/env python3
"""课评自动填写脚本 — 复旦大学课程评估自动化工具."""

import argparse
import sys
import time
from pathlib import Path

from src.config_loader import load_term_config, load_presets_config, build_evaluation_url
from src.browser_manager import BrowserManager
from src.authenticator import ensure_authenticated
from src.page_navigator import (
    navigate_to_tasks,
    extract_course_list,
    enter_course_evaluation,
    submit_evaluation,
    go_next_course,
    save_screenshot,
    dismiss_modal,
    detect_teacher_tabs,
    switch_to_teacher_tab,
    handle_reason_popups,
    accept_copy_previous_evaluation,
)
from src.question_detector import detect_questions
from src.answer_engine import generate_selections
from src.form_filler import fill_form
from src.reviewer import review_selections
from src.cli import prompt_sentiment, show_progress, print_banner, print_summary


def main():
    parser = argparse.ArgumentParser(
        description="复旦大学课评自动填写脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py                          # 默认保险模式，逐门确认
  python main.py -1 -y                    # 全部喜欢，自动提交
  python main.py -2 --dry-run             # 全部一般，干跑预览
  python main.py -3 -y --headless         # 全部讨厌，无头自动提交
  python main.py --semester 2026-2027-1   # 指定学期
  python main.py --ai                     # 启用 AI 模块
        """,
    )
    parser.add_argument("-1", dest="sentiment_like", action="store_true", help="全部课程使用「喜欢」情感")
    parser.add_argument("-2", dest="sentiment_neutral", action="store_true", help="全部课程使用「一般」情感")
    parser.add_argument("-3", dest="sentiment_dislike", action="store_true", help="全部课程使用「讨厌」情感")
    parser.add_argument("-y", action="store_true", help="自动提交，无需人为确认（等同 --no-confirm）")
    parser.add_argument("--semester", "-s", help="覆盖学期 (如 2026-2027-1)")
    parser.add_argument("--no-confirm", action="store_true", help="关闭保险模式，全自动运行")
    parser.add_argument("--confirm", action="store_true", help="强制开启保险模式")
    parser.add_argument("--ai", action="store_true", help="启用 AI 模块")
    parser.add_argument("--provider", help="AI provider (claude/openai)")
    parser.add_argument("--headless", action="store_true", help="无头模式运行浏览器")
    parser.add_argument("--dry-run", action="store_true", help="干跑模式：只打印选择，不填表不提交")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细日志")
    parser.add_argument("--config", "-c", default="term.yaml", help="配置文件路径 (默认 term.yaml)")
    args = parser.parse_args()

    # Resolve sentiment from CLI flags (-1/-2/-3)
    from src.models import Sentiment
    cli_sentiment = None
    if args.sentiment_dislike:
        cli_sentiment = Sentiment.DISLIKE
    elif args.sentiment_neutral:
        cli_sentiment = Sentiment.NEUTRAL
    elif args.sentiment_like:
        cli_sentiment = Sentiment.LIKE

    print_banner()

    # Resolve paths
    project_root = Path(__file__).parent
    config_dir = project_root / "config"
    data_dir = project_root / "data"
    storage_state = data_dir / "storage_state.json"
    screenshot_dir = data_dir / "screenshots"

    # Load configs
    print("[INFO] 加载配置...")
    term = load_term_config(config_dir, args.config)
    presets = load_presets_config(config_dir)

    evaluation_url = build_evaluation_url(term, args.semester)
    if args.verbose:
        print(f"  URL: {evaluation_url}")

    # Determine confirm mode
    confirm_mode = term.behavior.confirm_before_submit
    if args.no_confirm or args.y:
        confirm_mode = False
    if args.confirm:
        confirm_mode = True
    if args.dry_run:
        confirm_mode = False

    print(f"[INFO] 保险模式: {'开启' if confirm_mode else '关闭（全自动）'}")
    if args.dry_run:
        print("[INFO] 干跑模式: 不会实际操作页面")

    # Initialize AI writer if enabled
    ai_writer = None
    if args.ai or term.ai.enabled:
        print("[INFO] 初始化 AI 模块...")
        try:
            from src.ai.writer import AIWriter

            ai_config = term.ai
            if args.provider:
                ai_config.provider = args.provider
            ai_writer = AIWriter(ai_config)
            print(f"  [OK] AI 模块就绪 (provider={ai_config.provider}, model={ai_config.model})")
        except Exception as e:
            print(f"  [WARN] AI 模块初始化失败: {e}")
            print("  [INFO] 已降级为固定预设模式")

    # Start browser
    print("[INFO] 启动浏览器...")
    browser = BrowserManager(headless=args.headless, storage_state_path=storage_state)

    completed = 0
    skipped = 0
    errors: list[str] = []

    try:
        page = browser.start()

        # Authentication
        print("[INFO] 检查认证状态...")
        page = ensure_authenticated(page, evaluation_url, storage_state)

        # Navigate to task list
        navigate_to_tasks(page, evaluation_url)

        # Extract courses
        courses = extract_course_list(page, term)
        if not courses:
            print("[ERROR] 未找到任何待评价课程，请检查页面是否正常加载")
            sys.exit(1)

        print(f"\n[INFO] 找到 {len(courses)} 门待评价课程:")
        for i, c in enumerate(courses, 1):
            print(f"  {i}. {c}")

        total = len(courses)

        # Process each course
        for i, course_name in enumerate(courses, 1):
            show_progress(i, total)

            # Get sentiment (CLI flag overrides interactive prompt)
            if cli_sentiment:
                sentiment = cli_sentiment
                emoji_map = {Sentiment.LIKE: "😊", Sentiment.NEUTRAL: "😐", Sentiment.DISLIKE: "😠"}
                print(f"  情感: {sentiment.value} {emoji_map.get(sentiment, '')}")
            else:
                sentiment = prompt_sentiment(course_name, i, total)
                if sentiment is None:
                    print(f"  → 跳过 {course_name}")
                    skipped += 1
                    continue

            # Find matching course config
            course_config = None
            for c in term.courses:
                if c.name in course_name or course_name in c.name:
                    course_config = c
                    break

            # Enter evaluation form
            print(f"  进入评价页面...")
            if not enter_course_evaluation(page, course_name):
                errors.append(f"{course_name}: 无法进入评价页面")
                continue

            # Dismiss any popup/modal that appears after entering
            time.sleep(0.3)
            if dismiss_modal(page):
                print(f"  已关闭弹出提示框")

            # Detect teacher tabs (multi-teacher courses)
            teacher_tabs = detect_teacher_tabs(page)
            if not teacher_tabs:
                teacher_tabs = [course_name]  # Single teacher, use course name as label

            teacher_skipped = False
            for t_idx, teacher_name in enumerate(teacher_tabs):
                if t_idx > 0:
                    print(f"\n  --- 切换至教师 [{t_idx+1}/{len(teacher_tabs)}]: {teacher_name} ---")
                    if not switch_to_teacher_tab(page, t_idx):
                        print(f"  [WARN] 无法切换到教师 '{teacher_name}'，跳过")
                        continue
                    # Accept "copy previous evaluation" popup
                    accept_copy_previous_evaluation(page)

                if len(teacher_tabs) > 1:
                    print(f"  教师 [{t_idx+1}/{len(teacher_tabs)}]: {teacher_name}")

                # Detect questions for this teacher/sheet
                questions = detect_questions(page, term, verbose=args.verbose)
                if not questions:
                    print(f"  [WARN] {teacher_name}: 未检测到题目，跳过")
                    continue

                # Generate selections
                selections = generate_selections(questions, sentiment, presets, term, course_config, ai_writer)

                if args.verbose:
                    for sel in selections:
                        q = next((q for q in questions if q.index == sel.question_index), None)
                        title = q.title if q else "?"
                        opt = q.options[sel.option_index].label if q and sel.option_index < len(q.options) else "?"
                        qtype = q.detected_type.value if q else "?"
                        print(f"  [{sel.question_index}] [{qtype}] {title} → {opt}" + (f' + "{sel.text}"' if sel.text else ""))

                # Review (if in confirm mode)
                review_label = f"{course_name} / {teacher_name}" if len(teacher_tabs) > 1 else course_name
                if confirm_mode:
                    selections = review_selections(review_label, questions, selections)
                    if selections is None:
                        print(f"  → 跳过 {review_label}")
                        teacher_skipped = True
                        continue

                # Dry run: just print
                if args.dry_run:
                    print(f"  [DRY-RUN] {review_label} 将提交 {len(selections)} 个选项")
                    for sel in selections:
                        q = next((q for q in questions if q.index == sel.question_index), None)
                        title = q.title if q else "?"
                        opt_label = q.options[sel.option_index].label if q and sel.option_index < len(q.options) else "?"
                        qtype = q.detected_type.value if q else "?"
                        opts_preview = [o.label for o in q.options] if q else []
                        text_info = f' + "{sel.text}"' if sel.text else ""
                        print(f"    [{sel.question_index}] [{qtype}] {title} → {opt_label}{text_info}")
                        if len(opts_preview) != 5:
                            print(f"          选项: {opts_preview}")
                    continue

                # Fill form
                print(f"  填写表单...")
                fallback = term.text_presets.get(sentiment.value, [None])[0] if term.text_presets else None
                fill_form(page, selections, fallback_text=fallback, sentiment=sentiment.value, questions=questions)

                # Screenshot before submit
                save_screenshot(page, screenshot_dir, f"pre_submit_{i:02d}_{course_name}_{t_idx}")

            # After all teachers, submit or close
            if teacher_skipped:
                print(f"  [WARN] 有教师被跳过，跳过提交 {course_name}")
                errors.append(f"{course_name}: 部分教师未完成")
                dismiss_modal(page)
                navigate_to_tasks(page, evaluation_url, force=True)
                continue

            if args.dry_run:
                completed += 1
                dismiss_modal(page)
                navigate_to_tasks(page, evaluation_url, force=True)
                continue

            # Submit
            print(f"  提交评价...")
            if submit_evaluation(page):
                # Handle reason popups (extreme ratings trigger written justification)
                handle_reason_popups(page, sentiment.value)
                print(f"  [OK] {course_name} 提交成功")
                completed += 1
                if not confirm_mode and i < total:
                    advanced = go_next_course(page)
                    if advanced:
                        time.sleep(2)
                        continue
                dismiss_modal(page)
                navigate_to_tasks(page, evaluation_url, force=True)
            else:
                errors.append(f"{course_name}: 提交失败")
                save_screenshot(page, screenshot_dir, f"error_{i:02d}_{course_name}")
                dismiss_modal(page)
                navigate_to_tasks(page, evaluation_url, force=True)

    except KeyboardInterrupt:
        print("\n[INFO] 用户中断")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        errors.append(str(e))
    finally:
        browser.close()

    print_summary(completed, skipped, errors)


if __name__ == "__main__":
    main()
