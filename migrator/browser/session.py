"""Plain Playwright browser session with shared observation and action tools."""

from contextlib import asynccontextmanager
import re

from playwright.async_api import async_playwright


ACTIONS = frozenset({"click", "fill", "select", "check", "uncheck", "press"})
REF_PATTERN = re.compile(r"\[ref=([a-zA-Z0-9]+)\]")


class BrowserActionError(ValueError):
    """Fixed, non-sensitive action failure safe to return to the model."""


class BrowserSession:
    def __init__(self, page):
        self.page = page
        self._refs: set[str] = set()
        self._observed_url = ""
        page.on("popup", self._on_popup)

    def _on_popup(self, page) -> None:
        self.page = page
        self.invalidate_refs()
        page.on("popup", self._on_popup)

    def check_page(self) -> None:
        if self.page.is_closed():
            raise BrowserActionError("Browser page is closed")

    def invalidate_refs(self) -> None:
        self._refs.clear()

    async def observe(self, offset: int = 0) -> dict:
        self.check_page()
        self.invalidate_refs()

        page = self.page

        await page.wait_for_load_state("load")
        await page.wait_for_timeout(250)

        url = page.url
        snapshot = await page.aria_snapshot(mode="ai")

        if self.page != page or page.url != url:
            raise BrowserActionError("Page changed during observation; observe again")

        self.check_page()

        next_offset = offset + 20_000 if offset + 20_000 < len(snapshot) else None
        snapshot = snapshot[offset:offset + 20_000]

        self._refs = set(REF_PATTERN.findall(snapshot))
        self._observed_url = url

        return {
            "url": url,
            "snapshot": snapshot,
            "truncated": next_offset is not None,
            "next_offset": next_offset,
        }


    async def action(self, action: str, ref: str, value: str | None) -> dict:
        self.check_page()
        if action not in ACTIONS:
            raise BrowserActionError("Unsupported browser action")
        if ref not in self._refs or self.page.url != self._observed_url:
            raise BrowserActionError("Reference is not in the current snapshot; observe again")
        if action in ("fill", "select", "press"):
            if value is None:
                raise BrowserActionError("This action requires a value")
        elif value is not None:
            raise BrowserActionError("This action requires value=null")
        target = self.page.get_by_ref(ref)
        self.invalidate_refs()
        if action == "fill":
            await target.fill(value)
        elif action == "click":
            if await target.get_attribute("target") == "_blank":
                async with self.page.expect_popup() as popup:
                    await target.click()
                opened_page = await popup.value
                if self.page != opened_page:
                    self._on_popup(opened_page)
            else:
                await target.click()
        elif action == "select":
            await target.select_option(label=value)
        elif action in ("check", "uncheck"):
            await target.set_checked(action == "check")
        elif action == "press":
            if value not in ("Enter", "Tab", "Escape", "ArrowDown", "ArrowUp", "Space"):
                raise BrowserActionError("Only navigation keys and Enter are supported")
            await target.press(value)
        return {"action": action, "observation": await self.observe()}


@asynccontextmanager
async def open_browser(login_url: str, *, headless: bool = False):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=headless)
        try:
            context = await browser.new_context()
            context.set_default_timeout(10_000)
            context.set_default_navigation_timeout(30_000)
            page = await context.new_page()
            await page.goto(login_url, wait_until="domcontentloaded")
            yield BrowserSession(page)
        finally:
            await browser.close()
