import time
from pathlib import Path

from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page, TimeoutError as PwTimeout


class BrowserManager:
    def __init__(self, headless: bool = False, storage_state_path: Path | None = None):
        self._headless = headless
        self._storage_state_path = storage_state_path
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    @property
    def page(self) -> Page:
        if not self._context or len(self._context.pages) == 0:
            raise RuntimeError("浏览器未启动或没有打开的页面")
        return self._context.pages[0]

    def new_page(self) -> Page:
        if not self._context:
            raise RuntimeError("浏览器上下文未初始化")
        return self._context.new_page()

    def start(self) -> Page:
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self._headless)

        if self._storage_state_path and self._storage_state_path.exists():
            self._context = self._browser.new_context(
                storage_state=str(self._storage_state_path)
            )
        else:
            self._context = self._browser.new_context()

        page = self.new_page()

        # Auto-dismiss browser-native dialogs (alert, confirm, prompt)
        page.on("dialog", lambda dialog: dialog.accept())

        return page

    def save_storage_state(self) -> None:
        if self._context and self._storage_state_path:
            self._storage_state_path.parent.mkdir(parents=True, exist_ok=True)
            self._context.storage_state(path=str(self._storage_state_path))

    def close(self) -> None:
        if self._context:
            self._context.close()
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()

    def retry_on_timeout(self, func, max_retries: int = 3, base_delay: float = 2.0):
        for attempt in range(max_retries):
            try:
                return func()
            except (PwTimeout, Exception) as e:
                if attempt == max_retries - 1:
                    raise
                delay = base_delay * (2 ** attempt)
                print(f"  [WARN] 操作超时，{delay:.0f}s 后重试... ({attempt + 1}/{max_retries})")
                time.sleep(delay)
