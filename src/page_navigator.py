import re
import time
from pathlib import Path

from playwright.sync_api import Page, TimeoutError as PwTimeout

from .models import TermConfig


def navigate_to_tasks(page: Page, url: str, force: bool = False) -> None:
    # Skip if already at the target (e.g., after auth check)
    if not force and (page.url == url or page.url.startswith(url.split("?")[0])):
        print(f"[INFO] 已在目标页面，跳过导航")
        return

    print(f"[INFO] 导航到: {url}")
    try:
        page.goto(url, wait_until="networkidle", timeout=30000)
    except PwTimeout:
        # Vue SPA sometimes keeps websocket open, networkidle may never fire
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
    time.sleep(3)


def dismiss_modal(page: Page) -> bool:
    """Close any open dialog/modal (e.g., evaluation popup, alert, confirm).

    Returns True if a modal was found and dismissed, False otherwise.
    """
    # Strategy 1: click confirm/close buttons (ordered by specificity)
    confirm_selectors = [
        # Ant Design confirm modal
        ".ant-modal-confirm .ant-btn-primary",
        ".ant-modal-confirm-btns .ant-btn",
        ".ant-modal-footer .ant-btn-primary",
        ".ant-modal-close",
        # Element UI dialogs
        ".el-message-box__btns .el-button--primary",
        ".el-dialog__footer .el-button--primary",
        ".el-message-box__close",
        ".el-dialog__close",
        ".el-dialog__headerbtn",
        # Generic buttons
        "button:has-text('知道了')",
        "button:has-text('确定')",
        "button:has-text('确 定')",
        "button:has-text('OK')",
        "button:has-text('关闭')",
        "button:has-text('取消')",
        "button:has-text('返回')",
        "button:has-text('返 回')",
        "span:has-text('取消')",
        "[class*='close']",
        "[class*='cancel']",
    ]

    for selector in confirm_selectors:
        try:
            btn = page.locator(selector).first
            if btn.count() > 0 and btn.is_visible():
                btn.click()
                time.sleep(0.5)
                return True
        except Exception:
            continue

    # Strategy 2: press Enter (often confirms default button in modals)
    try:
        page.keyboard.press("Enter")
        time.sleep(0.5)
        modal_indicators = page.locator(".ant-modal-wrap, .ant-modal-mask, .el-dialog__wrapper, .el-message-box__wrapper").first
        if modal_indicators.count() == 0 or not modal_indicators.is_visible():
            return True
    except Exception:
        pass

    # Strategy 3: press Escape
    try:
        page.keyboard.press("Escape")
        time.sleep(1)
    except Exception:
        pass

    return False


def extract_course_list(page: Page, term: TermConfig) -> list[str]:
    """Extract unfinished course names from the task list page."""
    selectors_to_try = [
        term.selectors.course_list_container,
        ".course-name",
        ".task-course-name",
        "a[class*='course']",
        "tbody tr td:first-child",
        "tr td:nth-child(2)",
        ".el-table__body-wrapper .el-table__row td:first-child",
    ]

    courses = []
    for selector in selectors_to_try:
        if not selector:
            continue
        try:
            elements = page.locator(selector).all()
            names = [
                el.inner_text().strip()
                for el in elements
                if el.inner_text().strip()
            ]
            names = _filter_valid_courses(names)
            if names:
                courses = names
                break
        except Exception:
            continue

    if not courses:
        print("[WARN] 未能自动检测课程列表，请检查 selectors 配置")
        _dump_page_elements(page)
    return courses


def _filter_valid_courses(names: list[str]) -> list[str]:
    """Filter out text that doesn't look like a course name."""
    # Course names typically have Chinese characters, are 3-30 chars,
    # and don't look like headers/buttons
    filtered = []
    skip_patterns = [
        r"^[序号#\d]+$",        # Pure numbers / "序号"
        r"^(操作|状态|提交|保存)$",  # UI labels
        r"^(已|未).*",           # Status labels
    ]
    for name in names:
        if len(name) < 2 or len(name) > 60:
            continue
        if any(re.match(p, name) for p in skip_patterns):
            continue
        if not re.search(r'[一-鿿]', name):
            continue  # Must contain at least one Chinese character
        filtered.append(name)
    return filtered


def enter_course_evaluation(page: Page, course_name: str) -> bool:
    """Click the evaluation button for a specific course."""
    try:
        # Prefer exact text match, fallback to substring
        row = page.get_by_text(course_name, exact=True).first
        if row.count() == 0:
            row = page.get_by_text(course_name).first

        if row.count() == 0:
            print(f"  [WARN] 未找到课程 '{course_name}'")
            return False

        # Walk up to find the table row or container
        container = row.locator("xpath=ancestor::tr[1]")
        if container.count() == 0:
            container = row.locator("xpath=../../..")

        # Try explicit evaluate buttons in the container
        btn_texts = ["评价", "评估", "待评", "进入", "评教", "开始"]
        for btn_text in btn_texts:
            for tag in ["button", "a", "span"]:
                btn = container.locator(f"{tag}:has-text('{btn_text}')").first
                if btn.count() > 0:
                    try:
                        if btn.is_visible():
                            print(f"  点击 '{btn_text}' 按钮")
                            old_url = page.url
                            btn.click()
                            time.sleep(4)
                            if _page_changed(page, old_url):
                                return True
                    except Exception:
                        continue

        # Fallback: try to click the course name as a link
        for tag in ["a", "span", "td"]:
            link = container.locator(f"{tag}:has-text('{course_name}')").first
            if link.count() > 0:
                try:
                    print(f"  点击课程名称链接")
                    old_url = page.url
                    link.click()
                    time.sleep(4)
                    if _page_changed(page, old_url):
                        return True
                except Exception:
                    continue

        # Last resort: click the row
        print(f"  尝试点击课程行")
        old_url = page.url
        row.click()
        time.sleep(4)
        if _page_changed(page, old_url):
            return True

        print(f"  [WARN] 点击后页面未跳转，可能需要在浏览器中手动操作")
        _dump_course_row(page, container)
    except Exception as e:
        print(f"  [WARN] 无法进入课程 '{course_name}': {e}")
    return False


def _page_changed(page: Page, old_url: str) -> bool:
    """Check if navigation occurred after a click."""
    new_url = page.url
    if new_url != old_url:
        return True
    # Also check if any radio buttons appeared (SPA might update URL hash slowly)
    if page.locator('input[type="radio"]').count() > 0:
        return True
    return False


def _dump_course_row(page: Page, container) -> None:
    """Debug: show what's in the course row."""
    print("  [DEBUG] 课程行结构:")
    try:
        html = container.inner_html()[:500]
        print(f"  HTML: {html}")
        for tag in ["button", "a", "span", "td", "div"]:
            elements = container.locator(tag).all()[:5]
            for el in elements:
                try:
                    txt = el.inner_text().strip()
                    if txt and len(txt) < 50:
                        print(f"  <{tag}>: {txt}")
                except Exception:
                    pass
    except Exception:
        pass


def submit_evaluation(page: Page) -> bool:
    """Click the submit button on the evaluation form."""
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
                time.sleep(1.5)
                return True
        except Exception:
            continue
    return False


def go_next_course(page: Page) -> bool:
    """After submitting, navigate to the next course."""
    next_selectors = [
        "button:has-text('下一题')",
        "button:has-text('下一门')",
        "button:has-text('继续')",
        "[class*='next']",
    ]
    for selector in next_selectors:
        try:
            btn = page.locator(selector).first
            if btn.is_visible():
                btn.click()
                time.sleep(3)
                return True
        except Exception:
            continue
    return False


def accept_copy_previous_evaluation(page: Page) -> bool:
    """After switching to a new teacher tab, check for a popup offering to
    copy/reuse the previous teacher's evaluation, and accept it.

    Returns True if the popup was found and accepted.
    """
    time.sleep(0.5)
    accept_selectors = [
        "button:has-text('使用前一位老师的评价')",
        "button:has-text('套用')",
        "button:has-text('应用前一位')",
        "button:has-text('复制前一位')",
        "button:has-text('沿用')",
        ".ant-modal-confirm .ant-btn-primary",
        ".ant-modal-footer .ant-btn-primary:has-text('是')",
        ".ant-modal-footer .ant-btn-primary:has-text('确定')",
        "button:has-text('是')",
        ".el-message-box__btns .el-button--primary:has-text('确定')",
    ]

    for selector in accept_selectors:
        try:
            btn = page.locator(selector).first
            if btn.count() > 0 and btn.is_visible():
                print(f"  已套用前一位老师的评价")
                btn.click()
                time.sleep(1)
                return True
        except Exception:
            continue

    return False


def detect_teacher_tabs(page: Page) -> list[str]:
    """Detect multiple teacher evaluation tabs/sheets on the current page.

    Returns a list of teacher names (tab labels). If only 1 found, returns
    a single-element list.
    """
    tab_selectors = [
        ".ant-tabs-tab",           # Ant Design tabs
        ".el-tabs__item",          # Element UI tabs
        "[role='tab']",            # ARIA tabs
        ".tab-item",
        ".teacher-tab",
    ]

    for selector in tab_selectors:
        try:
            tabs = page.locator(selector).all()
            names = []
            for tab in tabs:
                try:
                    txt = tab.inner_text().strip()
                    if txt and len(txt) > 0:
                        names.append(txt)
                except Exception:
                    continue
            if len(names) >= 1:
                print(f"[INFO] 检测到 {len(names)} 个教师/标签页: {names}")
                return names
        except Exception:
            continue

    # No tabs found — single teacher
    return []


def switch_to_teacher_tab(page: Page, index: int) -> bool:
    """Switch to a specific teacher evaluation tab by index.

    Returns True if successful.
    """
    tab_selectors = [
        ".ant-tabs-tab",
        ".el-tabs__item",
        "[role='tab']",
        ".tab-item",
    ]

    for selector in tab_selectors:
        try:
            tabs = page.locator(selector).all()
            if index < len(tabs):
                tab = tabs[index]
                tab.click()
                time.sleep(1)
                return True
        except Exception:
            continue
    return False


def handle_reason_popups(page: Page, sentiment_value: str) -> bool:
    """After submit, check for reason-input popups (triggered by extreme ratings).

    When sentiment is neutral or dislike, the system may pop up dialogs asking
    for written reasons. Let the user fill them manually.

    Returns True if popups were found and handled.
    """
    if sentiment_value not in ("neutral", "dislike"):
        return False

    time.sleep(2)
    found_any = False

    # Check for modals with textareas or text inputs
    modal_selectors = [
        ".ant-modal-wrap:visible",
        ".ant-modal:visible",
        ".el-dialog__wrapper:visible",
        ".el-message-box__wrapper:visible",
    ]

    for modal_sel in modal_selectors:
        try:
            modal = page.locator(modal_sel).first
            if modal.count() == 0 or not modal.is_visible():
                continue

            text_inputs = modal.locator('textarea, input[type="text"]').all()
            if not text_inputs:
                continue

            found_any = True
            print(f"\n  ⚠ 系统要求填写评价理由（情感={sentiment_value}）")

            for inp in text_inputs:
                try:
                    if inp.is_visible():
                        placeholder = inp.get_attribute("placeholder") or ""
                        if placeholder:
                            print(f"  提示: {placeholder[:80]}")
                        user_text = input("  请输入理由（回车跳过）: ").strip()
                        if user_text:
                            inp.fill(user_text)
                            time.sleep(0.3)
                except Exception:
                    continue

            # Click confirm/submit button in the modal
            confirm_btns = [
                ".ant-modal-footer .ant-btn-primary",
                ".el-dialog__footer .el-button--primary",
                ".el-message-box__btns .el-button--primary",
                "button:has-text('确定')",
                "button:has-text('提交')",
                "button:has-text('保存')",
            ]
            for btn_sel in confirm_btns:
                try:
                    btn = modal.locator(btn_sel).first
                    if btn.count() > 0 and btn.is_visible():
                        btn.click()
                        time.sleep(2)
                        break
                except Exception:
                    continue
        except Exception:
            continue

    return found_any


def save_screenshot(page: Page, screenshot_dir: Path, name: str) -> None:
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    path = screenshot_dir / f"{name}.png"
    page.screenshot(path=str(path))


def _dump_page_elements(page: Page) -> None:
    """Print available elements on task list page to help debug selectors."""
    print("[DEBUG] 任务列表页面元素分析:")
    try:
        for tag in ["a", "td", "span", "div"]:
            elements = page.locator(tag).all()
            texts = []
            for el in elements[:20]:
                try:
                    t = el.inner_text().strip()
                    if 2 < len(t) < 40:
                        texts.append(t)
                except Exception:
                    pass
            if texts:
                print(f"  <{tag}> 文本: {texts[:10]}")

        buttons = page.locator("button, a[class*='btn']").all()
        btn_texts = []
        for b in buttons[:10]:
            try:
                t = b.inner_text().strip()
                if t:
                    btn_texts.append(t)
            except Exception:
                pass
        if btn_texts:
            print(f"  按钮/链接: {btn_texts}")
    except Exception as e:
        print(f"  [DEBUG] 诊断失败: {e}")
