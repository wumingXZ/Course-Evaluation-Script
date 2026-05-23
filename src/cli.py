import sys

from .models import Sentiment


SENTIMENT_MAP = {
    "1": Sentiment.LIKE,
    "2": Sentiment.NEUTRAL,
    "3": Sentiment.DISLIKE,
}

SENTIMENT_LABELS = {
    Sentiment.LIKE: "喜欢 😊",
    Sentiment.NEUTRAL: "一般 😐",
    Sentiment.DISLIKE: "讨厌 😞",
}


def prompt_sentiment(course_name: str, current: int, total: int) -> Sentiment | None:
    """Ask user for sentiment toward a specific course.

    Returns None if user wants to skip or quit.
    """
    print(f"\n{'─' * 40}")
    print(f"  课程 [{current}/{total}]: {course_name}")
    print(f"  请选择你对这门课的态度:")
    print(f"    1. 喜欢   (正面评价为主，无负面)")
    print(f"    2. 一般   (中性为主，最多1题负面)")
    print(f"    3. 讨厌   (负面评价为主)")
    print(f"    s. 跳过此课程")
    print(f"    q. 退出脚本")

    while True:
        choice = input("  > ").strip().lower()
        if choice in SENTIMENT_MAP:
            sent = SENTIMENT_MAP[choice]
            print(f"  → {SENTIMENT_LABELS[sent]}")
            return sent
        elif choice == "s":
            return None
        elif choice == "q":
            print("\n[INFO] 用户退出")
            sys.exit(0)
        else:
            print("  请输入 1/2/3/s/q")


def show_progress(current: int, total: int) -> None:
    bar_len = 20
    filled = int(bar_len * current / total) if total > 0 else bar_len
    bar = "█" * filled + "░" * (bar_len - filled)
    print(f"\n  进度: [{bar}] {current}/{total}")


def print_banner() -> None:
    print(r"""
  ╔══════════════════════════════════════╗
  ║       课评自动填写脚本 v1.0          ║
  ║   复旦大学课程评估自动化工具          ║
  ╚══════════════════════════════════════╝
  """)


def print_summary(completed: int, skipped: int, errors: list[str]) -> None:
    print(f"\n{'=' * 40}")
    print(f"  完成: {completed} 门课程")
    if skipped:
        print(f"  跳过: {skipped} 门课程")
    if errors:
        print(f"  错误: {len(errors)} 项")
        for e in errors:
            print(f"    - {e}")
    print(f"{'=' * 40}")
