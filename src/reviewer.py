import sys

from .models import Selection, Question


def review_selections(
    course_name: str,
    questions: list[Question],
    selections: list[Selection],
) -> list[Selection] | None:
    """Present selections to user and allow confirmation or modification.

    Returns:
        Modified list of Selection if user confirms, None to skip, or exits.
    """
    while True:
        _print_selections(course_name, questions, selections)

        print()
        print("  [Enter] 确认提交  [m] 修改  [s] 跳过此课程  [q] 退出")
        choice = input("  > ").strip().lower()

        if choice == "":
            return selections
        elif choice == "m":
            selections = _modify_mode(questions, selections)
        elif choice == "s":
            return None
        elif choice == "q":
            print("\n[INFO] 用户退出")
            sys.exit(0)
        else:
            print("  未知命令")


def _print_selections(course_name: str, questions: list[Question], selections: list[Selection]) -> None:
    print(f"\n{'=' * 60}")
    print(f"  课程: {course_name}")
    print(f"  题目数: {len(selections)}")
    print(f"{'=' * 60}")

    for sel in selections:
        q = _find_question(questions, sel.question_index)
        title = q.title if q else "?"
        opt_label = ""
        if q and sel.option_index < len(q.options):
            opt_label = q.options[sel.option_index].label
        text_hint = f' + "{sel.text}"' if sel.text else ""
        print(f"  [{sel.question_index}] {title}")
        print(f"      → {opt_label}{text_hint}")


def _find_question(questions: list[Question], index: int) -> Question | None:
    for q in questions:
        if q.index == index:
            return q
    return None


def _modify_mode(questions: list[Question], selections: list[Selection]) -> list[Selection]:
    print("\n  修改模式 - 输入格式:")
    print("    题号→选项号    如: 3→4  (将第3题改为第4个选项)")
    print("    题号 文字 内容  如: 5 文字 讲得很好")
    print("    done           退出修改模式")
    print()

    # Build a mutable lookup
    sel_map: dict[int, Selection] = {}
    for s in selections:
        sel_map[s.question_index] = s

    while True:
        cmd = input("  mod > ").strip()
        if cmd.lower() == "done":
            break

        if "→" in cmd or "->" in cmd:
            parts = cmd.replace("->", "→").split("→")
            try:
                q_idx = int(parts[0].strip())
                opt_idx = int(parts[1].strip())
                if q_idx in sel_map:
                    sel_map[q_idx].option_index = opt_idx
                    sel_map[q_idx].text = None  # Clear text when option changes
                    print(f"  [OK] 第{q_idx}题 → 选项{opt_idx}")
                else:
                    print(f"  [WARN] 题目 {q_idx} 不在当前选择中")
            except ValueError:
                print("  格式错误，请用: 题号→选项号")

        elif "文字" in cmd:
            parts = cmd.split("文字", 1)
            try:
                q_idx = int(parts[0].strip())
                text = parts[1].strip()
                if q_idx in sel_map:
                    sel_map[q_idx].text = text
                    print(f"  [OK] 第{q_idx}题文本已更新")
                else:
                    print(f"  [WARN] 题目 {q_idx} 不在当前选择中")
            except ValueError:
                print("  格式错误，请用: 题号 文字 内容")
        else:
            print("  未知命令，请用: 题号→选项号 或 题号 文字 内容")

    return list(sel_map.values())
