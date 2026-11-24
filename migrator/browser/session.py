"""Plain Playwright browser session with shared observation and action tools."""

from contextlib import asynccontextmanager
import re
from pathlib import Path
from uuid import uuid4

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


    async def download(self, ref: str, directory: Path) -> dict:
        self.check_page()
        if ref not in self._refs or self.page.url != self._observed_url:
            raise BrowserActionError("Reference is not in the current snapshot; observe again")
        target = self.page.get_by_ref(ref)
        if not await target.is_enabled():
            raise BrowserActionError(
                "Control is disabled; no action was performed. Open its associated input or "
                "wait for a state change, then use the enabled control from a fresh snapshot."
            )
        self.invalidate_refs()
        async with self.page.expect_download(timeout=60_000) as pending:
            await target.click()
        download = await pending.value
        directory.mkdir(parents=True, exist_ok=True)
        # Keep the vendor filename as metadata, never as a filesystem path.
        filename = uuid4().hex + ".csv"
        await download.save_as(directory / filename)
        return {"path": filename, "suggested_filename": download.suggested_filename}

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
        if not await target.is_enabled():
            raise BrowserActionError(
                "Control is disabled; no action was performed. Open its associated input or "
                "wait for a state change, then use the enabled control from a fresh snapshot."
            )
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
        browser = await playwright.chromium.launch(
            headless=headless, args=[] if headless else ["--window-size=1600,1000"]
        )
        try:
            context = await browser.new_context(no_viewport=not headless)
            context.set_default_timeout(10_000)
            context.set_default_navigation_timeout(30_000)
            page = await context.new_page()
            await page.goto(login_url, wait_until="domcontentloaded")
            yield BrowserSession(page)
        finally:
            await browser.close()
