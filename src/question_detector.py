from playwright.sync_api import Page, Locator

from .models import Question, Option, QuestionType, TermConfig
from .dom_utils import (
    extract_all_questions,
    extract_checkbox_questions,
    get_radio_groups,
    get_checkbox_groups,
    scan_all_form_elements,
)


REVERSE_KEYWORDS = ["反向"]
YES_LABELS = {"是", "yes", "y", "1"}
NO_LABELS = {"否", "no", "n", "0"}


def detect_questions(page: Page, term: TermConfig, verbose: bool = False) -> list[Question]:
    """Scan the page DOM and build a list of detected questions."""
    raw_questions = extract_all_questions(page)
    if not raw_questions:
        print("[WARN] 页面上未找到任何 radio 按钮")
        _dump_page_debug(page)
        return []

    # Optional container filtering
    container_selector = term.selectors.question_container
    if container_selector:
        containers = page.locator(container_selector).all()
        if not containers:
            print(f"[WARN] 选择器 '{container_selector}' 未匹配")

    questions: list[Question] = []
    q_index = 0

    for data in raw_questions:
        options = [
            Option(
                index=i,
                label=opt["label"],
                has_text_input=opt.get("has_text_input", False),
            )
            for i, opt in enumerate(data["options"])
        ]

        is_reverse, is_yesno = _detect_type(options)
        has_textfill = any(o.has_text_input for o in options)

        if not has_textfill:
            all_labels = " ".join(o.label for o in options)
            if any(kw in all_labels for kw in ["推荐", "recommend", "建议", "suggest"]):
                has_textfill = True

        question_type = QuestionType.FORWARD
        if is_yesno:
            question_type = QuestionType.YESNO
        elif is_reverse:
            question_type = QuestionType.REVERSE

        questions.append(Question(
            index=q_index,
            title=data.get("title", "未知题目"),
            options=options,
            detected_type=question_type,
            is_reverse=is_reverse,
            is_yesno=is_yesno,
            has_textfill=has_textfill,
            was_reversed=data.get("_was_reversed", False),
        ))
        q_index += 1

    # Checkbox questions
    raw_checkboxes = extract_checkbox_questions(page)
    for data in raw_checkboxes:
        options = [
            Option(
                index=i,
                label=opt["label"],
                has_text_input=opt.get("has_text_input", False),
            )
            for i, opt in enumerate(data["options"])
        ]
        questions.append(Question(
            index=q_index,
            title=data.get("title", "未知题目"),
            options=options,
            detected_type=QuestionType.CHECKBOX,
            is_reverse=False,
            is_yesno=False,
            has_textfill=False,
        ))
        q_index += 1

    print(f"[INFO] 检测到 {len(questions)} 道题目 (radio: {len(raw_questions)}, checkbox: {len(raw_checkboxes)})")

    if verbose:
        form_scan = scan_all_form_elements(page)
        form_items = form_scan.get("item_summary", [])
        if form_items:
            for fi in form_items:
                flag = " ← 非radio!" if 'radio' not in fi['types'] else ""
                print(f"  [{fi['idx']}] [{fi['types']}] radios={fi['radioCount']} {fi['label'][:60]}{flag}")
        if questions:
            q0 = questions[0]
            labels = [o.label for o in q0.options]
            print(f"  [DEBUG] Q0 选项顺序: {labels}")
        if all(q.title == '未知题目' for q in questions):
            dump_radio_ancestry(page)
            _dump_page_structure(page)

    return questions


def _detect_type(options: list[Option]) -> tuple[bool, bool]:
    labels_lower = [o.label.lower() for o in options]
    all_text = " ".join(labels_lower)

    has_yes = any(l in YES_LABELS for l in labels_lower)
    has_no = any(l in NO_LABELS for l in labels_lower)
    if len(options) == 2 and has_yes and has_no:
        return False, True

    is_reverse = any(kw in all_text for kw in REVERSE_KEYWORDS)
    return is_reverse, False


# ── Debug utilities (only called in verbose mode) ──────────────────────────

def dump_radio_ancestry(page: Page) -> None:
    info = page.evaluate(
        """() => {
            const r = document.querySelector('input[type="radio"]');
            if (!r) return 'No radio found';
            const chain = [];
            let el = r;
            for (let i = 0; i < 10; i++) {
                chain.push({
                    level: i, tag: el.tagName,
                    cls: (el.className || '').toString().slice(0, 80),
                    id: el.id || '',
                    textSample: (el.textContent || '').trim().slice(0, 100),
                });
                el = el.parentElement;
                if (!el || el === document.body) break;
            }
            return chain;
        }"""
    )
    print("[DEBUG] 第一个 radio 的 DOM 层级结构:")
    for item in info:
        print(f"  L{item['level']}: <{item['tag']}> class={item['cls']} id={item['id']}")
        print(f"         text: {item['textSample'][:80]}")


def _dump_page_structure(page: Page) -> None:
    info = page.evaluate(
        """() => {
            const result = [];
            const contents = document.querySelectorAll('[class*="index__content"]');
            contents.forEach((content, i) => {
                const parent = content.parentElement;
                const siblings = [];
                if (parent) {
                    for (const child of parent.children) {
                        if (child === content) {
                            siblings.push('>>> [THIS CONTENT]');
                        } else {
                            siblings.push({
                                tag: child.tagName,
                                cls: (child.className || '').toString().slice(0, 60),
                                text: child.textContent.trim().slice(0, 80),
                            });
                        }
                    }
                }
                result.push({contentIdx: i, siblings: siblings.slice(0, 8)});
                if (i >= 2) return;
            });
            return result.slice(0, 3);
        }"""
    )
    print("[DEBUG] 页面结构分析（前3个内容容器）:")
    for item in info:
        for s in item.get('siblings', []):
            if isinstance(s, str):
                print(f"    {s}")
            else:
                print(f"    <{s['tag']}> class={s['cls']} text={s['text'][:60]}")


def _dump_page_debug(page: Page) -> None:
    print("[DEBUG] 页面诊断:")
    try:
        print(f"  URL: {page.url}")
        for tag in ["input", "button", "label", "textarea"]:
            print(f"  <{tag}>: {page.locator(tag).count()} 个")
        buttons = page.locator("button").all()
        visible_texts = [b.inner_text().strip() for b in buttons if b.is_visible()]
        if visible_texts:
            print(f"  可见按钮: {visible_texts}")
    except Exception as e:
        print(f"  [DEBUG] 诊断失败: {e}")
