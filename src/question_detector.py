from playwright.sync_api import Page, Locator

from .models import Question, Option, QuestionType, TermConfig
from .dom_utils import (
    extract_all_questions,
    extract_checkbox_questions,
    get_radio_groups,
    get_checkbox_groups,
    scan_all_form_elements,
)


REVERSE_KEYWORDS = ["反向"]  # Only "反向" is reliably in question titles, not option labels
YES_LABELS = {"是", "yes", "y", "1"}
NO_LABELS = {"否", "no", "n", "0"}


def detect_questions(page: Page, term: TermConfig) -> list[Question]:
    """Scan the page DOM and build a list of detected questions.

    Uses a single page.evaluate() to extract all question data efficiently,
    then matches with locator-based groups for later click operations.
    """
    # Get structured data in one JS call
    raw_questions = extract_all_questions(page)
    if not raw_questions:
        print("[WARN] 页面上未找到任何 radio 按钮")
        _dump_page_debug(page)
        return []

    # Scan for non-radio form elements that might represent missed questions
    form_scan = scan_all_form_elements(page)
    form_items = form_scan.get("item_summary", [])
    if form_items:
        radio_items = [fi for fi in form_items if 'radio' in fi['types']]
        non_radio_items = [fi for fi in form_items if 'radio' not in fi['types']]
        print(f"[INFO] 页面 form-item 容器: {len(form_items)} 个 "
              f"(含 radio: {len(radio_items)}, 非 radio: {len(non_radio_items)})")
        for fi in form_items:
            flag = " ← 非radio!" if 'radio' not in fi['types'] else ""
            print(f"  [{fi['idx']}] [{fi['types']}] radios={fi['radioCount']} {fi['label'][:60]}{flag}")
    else:
        non_radio_count = form_scan.get("checkboxes", 0) + form_scan.get("selects", 0) + form_scan.get("textareas", 0)
        if non_radio_count > 0:
            print(f"[INFO] 页面还有非 radio 表单元素: "
                  f"checkbox={form_scan.get('checkboxes', 0)}, "
                  f"select={form_scan.get('selects', 0)}, "
                  f"textarea={form_scan.get('textareas', 0)}")
    radio_count = len(raw_questions)
    total_form_items = len(form_items)
    print(f"[INFO] radio组={radio_count}, form-item容器={total_form_items}")

    # Get locator groups (needed for fill_form later, must match index order)
    locator_groups = get_radio_groups(page)
    group_keys = list(locator_groups.keys())

    # Optional container filtering
    container_selector = term.selectors.question_container
    if container_selector:
        containers = page.locator(container_selector).all()
        if containers:
            print(f"[INFO] 找到 {len(containers)} 个题目容器（共 {len(raw_questions)} 组 radio）")
        else:
            print(f"[WARN] 选择器 '{container_selector}' 未匹配，使用全部 {len(raw_questions)} 组")

    questions: list[Question] = []
    q_index = 0

    for data in raw_questions:
        # Build Option models
        options = [
            Option(
                index=i,
                label=opt["label"],
                has_text_input=opt.get("has_text_input", False),
            )
            for i, opt in enumerate(data["options"])
        ]

        # Detect question type
        is_reverse, is_yesno = _detect_type(options)
        has_textfill = any(o.has_text_input for o in options)

        # Heuristic: recommendation questions with "推荐" often need text
        # when selecting extreme options (强烈推荐/强烈不推荐)
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

    # --- Checkbox questions ---
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

    total = len(questions)
    radio_count = len(raw_questions)
    cb_count = len(raw_checkboxes)
    print(f"[INFO] 检测到 {total} 道题目 (radio: {radio_count}, checkbox: {cb_count})")
    # Debug: show first question's option order to verify normalization
    if questions:
        q0 = questions[0]
        labels = [o.label for o in q0.options]
        print(f"  [DEBUG] Q0 标题: {q0.title[:80]}")
        print(f"  [DEBUG] Q0 类型: {q0.detected_type.value}, 选项数: {len(labels)}")
        print(f"  [DEBUG] Q0 选项顺序: {labels}")
    # Dump DOM if all titles are unknown
    if questions and all(q.title == '未知题目' for q in questions):
        dump_radio_ancestry(page)
        _dump_page_structure(page)
    return questions


def _dump_page_structure(page: Page) -> None:
    """Debug: show the overall page structure to find where question titles are."""
    info = page.evaluate(
        """() => {
            const result = [];
            // Find all content containers and show their context
            const contents = document.querySelectorAll('[class*="index__content"]');
            contents.forEach((content, i) => {
                const parent = content.parentElement;
                const parentTag = parent ? parent.tagName : 'none';
                const parentCls = parent ? (parent.className || '').toString().slice(0, 80) : '';
                // Siblings of this content container
                const siblings = [];
                if (parent) {
                    for (const child of parent.children) {
                        if (child === content) {
                            siblings.push('>>> [THIS CONTENT]');
                        } else {
                            const tag = child.tagName;
                            const cls = (child.className || '').toString().slice(0, 60);
                            const text = child.textContent.trim().slice(0, 80);
                            siblings.push({tag, cls, text});
                        }
                    }
                }
                result.push({
                    contentIdx: i,
                    parentTag,
                    parentCls,
                    siblings: siblings.slice(0, 8),
                });
                if (i >= 2) return;  // Only show first 3
            });
            return result.slice(0, 3);
        }"""
    )
    print("[DEBUG] 页面结构分析（前3个内容容器）:")
    for item in info:
        print(f"  容器 #{item['contentIdx']}: parent=<{item['parentTag']}> class={item['parentCls']}")
        for s in item.get('siblings', []):
            if isinstance(s, str):
                print(f"    {s}")
            else:
                print(f"    <{s['tag']}> class={s['cls']} text={s['text'][:60]}")


def _detect_type(options: list[Option]) -> tuple[bool, bool]:
    labels_lower = [o.label.lower() for o in options]
    all_text = " ".join(labels_lower)

    has_yes = any(l in YES_LABELS for l in labels_lower)
    has_no = any(l in NO_LABELS for l in labels_lower)
    if len(options) == 2 and has_yes and has_no:
        return False, True

    is_reverse = any(kw in all_text for kw in REVERSE_KEYWORDS)
    return is_reverse, False


def dump_radio_ancestry(page: Page) -> None:
    """Debug: dump DOM ancestry of the first radio button to diagnose title extraction."""
    info = page.evaluate(
        """() => {
            const r = document.querySelector('input[type="radio"]');
            if (!r) return 'No radio found';
            const chain = [];
            let el = r;
            for (let i = 0; i < 10; i++) {
                const tag = el.tagName;
                const cls = (el.className || '').toString().slice(0, 80);
                const id = el.id || '';
                const text = el.textContent ? el.textContent.trim().slice(0, 100) : '';
                const children = el.children ? Array.from(el.children).map(c => c.tagName + ':' + (c.className||'').toString().slice(0,40)).join(', ') : '';
                chain.push({level: i, tag, cls, id, textSample: text, childTags: children});
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
        print(f"         children: {item['childTags'][:120]}")


def _dump_page_debug(page: Page) -> None:
    """Print available elements on the page to help debug selector issues."""
    print("[DEBUG] 页面结构分析:")
    try:
        print(f"  URL: {page.url}")
        print(f"  Title: {page.title()}")

        for tag in ["input", "button", "label", "textarea"]:
            print(f"  <{tag}>: {page.locator(tag).count()} 个")
        for sel in ['input[type="radio"]', 'input[type="text"]', "form", "fieldset"]:
            print(f"  {sel}: {page.locator(sel).count()} 个")

        buttons = page.locator("button").all()
        visible_texts = [b.inner_text().strip() for b in buttons if b.is_visible()]
        if visible_texts:
            print(f"  可见按钮: {visible_texts}")

        radios = page.locator('input[type="radio"]').all()
        if radios:
            print(f"  前5个 radio 属性:")
            for r in radios[:5]:
                try:
                    print(f"    name={r.get_attribute('name') or '(无)'}, value={r.get_attribute('value') or '(无)'}")
                except Exception:
                    pass
    except Exception as e:
        print(f"  [DEBUG] 诊断失败: {e}")
