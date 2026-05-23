import time

from playwright.sync_api import Page, Locator

from .dom_utils import get_radio_groups, get_checkbox_groups, find_associated_text_input


def fill_form(
    page: Page,
    selections: list,
    fallback_text: str | None = None,
    sentiment: str | None = None,
    questions: list | None = None,
) -> None:
    """Fill the evaluation form based on generated selections.

    Handles both radio (single-select) and checkbox (multi-select) questions.
    Radio questions come first in indexing, followed by checkbox questions.

    When sentiment is 'neutral' or 'dislike', text inputs for low-rating reasons
    are handed over to the user for manual input.
    """
    radio_groups = get_radio_groups(page)
    checkbox_groups = get_checkbox_groups(page)

    if not radio_groups and not checkbox_groups:
        print("[WARN] 未找到任何表单元素，无法填表")
        return

    # Build lookup: question_index → was_reversed
    was_reversed_map: dict[int, bool] = {}
    if questions:
        for q in questions:
            if q.was_reversed:
                was_reversed_map[q.index] = True

    sorted_radio_names = list(radio_groups.keys())
    sorted_cb_names = list(checkbox_groups.keys())
    radio_count = len(sorted_radio_names)

    for sel in selections:
        if sel.question_index < radio_count:
            # --- Radio question ---
            name = sorted_radio_names[sel.question_index]
            radios = radio_groups[name]

            if sel.option_index >= len(radios):
                print(f"  [WARN] 选项索引 {sel.option_index} 超出范围 "
                      f"(题目 {sel.question_index}, 共 {len(radios)} 个选项)")
                continue

            # Map normalized index to raw page index
            raw_idx = sel.option_index
            if was_reversed_map.get(sel.question_index):
                raw_idx = len(radios) - 1 - sel.option_index

            target = radios[raw_idx]

            try:
                target.check()
                time.sleep(0.15)

                # Look for dynamically-appeared text input
                text_input = find_associated_text_input(page, target)
                if text_input:
                    if sentiment in ("neutral", "dislike"):
                        print(f"\n  ⚠ 题目 {sel.question_index} 需要填写理由（情感={sentiment}）")
                        user_text = input("  请输入理由: ").strip()
                        if user_text:
                            text_input.fill(user_text)
                    else:
                        fill_value = sel.text or fallback_text
                        if fill_value:
                            text_input.fill(fill_value)
                            if not sel.text:
                                print(f"  [INFO] 题目 {sel.question_index} 检测到条件文本输入，已填充默认文本")
                        else:
                            print(f"  [WARN] 题目 {sel.question_index} 发现文本输入框但无填充文本，"
                                  f"请手动填写或使用 --confirm 模式")
                elif sel.text:
                    text_input = _find_text_input_nearby(page, target)
                    if text_input:
                        text_input.fill(sel.text)
                    else:
                        print(f"  [WARN] 未找到题目 {sel.question_index} 的文本输入框")
            except Exception as e:
                print(f"  [WARN] 填写题目 {sel.question_index} 选项 {sel.option_index} 失败: {e}")

        else:
            # --- Checkbox question ---
            cb_index = sel.question_index - radio_count
            target_cb = None

            if cb_index < len(sorted_cb_names):
                name = sorted_cb_names[cb_index]
                checkboxes = checkbox_groups[name]
                if sel.option_index < len(checkboxes):
                    target_cb = checkboxes[sel.option_index]

            # Fallback: find checkbox by label text
            if target_cb is None:
                # Try to match by the option label from the selection
                all_cbs = page.locator('input[type="checkbox"]').all()
                # We don't have the label here, so just try by DOM position
                # within the form-item containers
                form_items = page.locator('.ant-form-item').all()
                radio_fi_count = radio_count if radio_count <= len(form_items) else 0
                target_fi_idx = sel.question_index  # question index = form-item index
                if target_fi_idx < len(form_items):
                    cbs_in_fi = form_items[target_fi_idx].locator('input[type="checkbox"]').all()
                    if sel.option_index < len(cbs_in_fi):
                        target_cb = cbs_in_fi[sel.option_index]

            if target_cb is None:
                print(f"  [WARN] checkbox题目 {sel.question_index} 选项 {sel.option_index} 未找到")
                continue

            try:
                if not target_cb.is_checked():
                    target_cb.check()
            except Exception as e:
                print(f"  [WARN] 勾选checkbox题目 {sel.question_index} 选项 {sel.option_index} 失败: {e}")


def click_submit(page: Page) -> bool:
    """Click the submit/save button on the evaluation form."""
    submit_selectors = [
        "button:has-text('提交')",
        "button:has-text('保存')",
        "[class*='submit']",
        ".el-button--primary",
        "button[type='submit']",
    ]
    for selector in submit_selectors:
        try:
            btn = page.locator(selector).first
            if btn.is_visible():
                btn.click()
                time.sleep(3)
                return True
        except Exception:
            continue
    return False


def _find_text_input_nearby(page: Page, radio_element: Locator) -> Locator | None:
    """Wider search for text inputs that may have appeared conditionally."""
    try:
        # Strategy 1: search the entire form-item for any text input
        form_item = radio_element.locator("xpath=ancestor::*[contains(@class, 'ant-form-item') or contains(@class, 'el-form-item')][1]")
        if form_item.count() > 0:
            for sel in ['input[type="text"]', "textarea", '[contenteditable="true"]']:
                inputs = form_item.locator(sel).all()
                for inp in inputs:
                    if inp.is_visible():
                        return inp

        # Strategy 2: search by vertical proximity (wider range)
        rb = radio_element.bounding_box()
        if rb:
            all_inputs = page.locator('input[type="text"], textarea').all()
            for inp in all_inputs:
                try:
                    bb = inp.bounding_box()
                    if bb and abs(bb["y"] - rb["y"]) < 200 and inp.is_visible():
                        return inp
                except Exception:
                    continue

        # Strategy 3: search all visible text inputs on page and pick closest
        all_visible = page.locator('input[type="text"]:visible, textarea:visible').all()
        if all_visible and radio_element.bounding_box():
            rb = radio_element.bounding_box()
            best = None
            best_dist = float("inf")
            for inp in all_visible:
                try:
                    bb = inp.bounding_box()
                    if bb:
                        dist = abs(bb["y"] - rb["y"])
                        if dist < best_dist:
                            best_dist = dist
                            best = inp
                except Exception:
                    continue
            if best and best_dist < 300:
                return best
    except Exception:
        pass
    return None
