import time
from pathlib import Path

from playwright.sync_api import Page

LOGIN_DOMAINS = [
    "cas.fudan.edu.cn",
    "uis.fudan.edu.cn",
    "login.fudan.edu.cn",
    "sso.fudan.edu.cn",
    "idp.fudan.edu.cn",
]

LOGIN_PAGE_INDICATORS = [
    "统一身份认证",
    "用户登录",
    "请登录",
    "账号登录",
    "CAS",
    "SSO",
]

# After SSO login, user may briefly land on these before the target app
INTERMEDIATE_DOMAINS = [
    "sso.fudan.edu.cn",
    "idp.fudan.edu.cn",
]


def _is_login_page(page: Page) -> bool:
    """Check if the current page is a login/SSO page."""
    try:
        url = page.url.lower()
        # URL-based check
        for domain in LOGIN_DOMAINS:
            if domain in url:
                return True
        # Content-based check: login indicators + password field present
        has_password_input = page.locator('input[type="password"]').count() > 0
        if not has_password_input:
            return False
        title = page.title()
        body_text = page.locator("body").inner_text()[:500]
        for indicator in LOGIN_PAGE_INDICATORS:
            if indicator in title or indicator in body_text:
                return True
        return False
    except Exception:
        return True


def _wait_for_page_ready(page: Page, timeout_ms: int = 10000) -> None:
    """Wait for SPA to render after navigation."""
    try:
        page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
    except Exception:
        pass
    # Wait for potential JS redirect
    try:
        page.wait_for_load_state("networkidle", timeout=3000)
    except Exception:
        pass
    time.sleep(2)


def ensure_authenticated(page: Page, target_url: str, storage_path: Path) -> Page:
    """Ensure we have an authenticated session.

    Returns the page (possibly a new one if the session was restored).
    """
    storage_path.parent.mkdir(parents=True, exist_ok=True)

    if storage_path.exists():
        # Try restoring session
        page.goto(target_url, wait_until="domcontentloaded")
        _wait_for_page_ready(page)

        if not _is_login_page(page):
            print("[INFO] 会话有效，跳过登录")
            return page
        print("[INFO] 已保存的会话已过期")

    # Manual login flow
    print("[INFO] 需要重新登录")
    page.goto(target_url, wait_until="domcontentloaded")

    print(f"\n  请在浏览器中完成 SSO 登录（5 分钟内）...")
    deadline = time.time() + 300
    while time.time() < deadline:
        time.sleep(2)
        if not _is_login_page(page):
            # Check it's not an intermediate SSO redirect
            url_lower = page.url.lower()
            if not any(d in url_lower for d in INTERMEDIATE_DOMAINS):
                print("  [OK] 登录成功")
                page.context.storage_state(path=str(storage_path))
                print(f"[INFO] 会话已保存到 {storage_path}")
                return page

    print("  [ERROR] 登录超时")
    raise RuntimeError("登录失败，无法继续")
