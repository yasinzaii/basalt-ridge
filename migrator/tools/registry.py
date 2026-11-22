
from pathlib import Path

from migrator.tools.browser import create_browser_tools
from migrator.tools.memory import create_memory_tools


def create_tools(browser, *, memory_directory: Path, allowed_actions=None):
    browser_tools, execute_browser = create_browser_tools(
        browser,
        allowed_actions=allowed_actions,
        memory_directory=memory_directory,
    )

    memory_tools, execute_memory = create_memory_tools(
        memory_directory
    )

    async def execute(name: str, arguments: dict) -> str:
        if name == "memory_load":
            browser.invalidate_refs()
            return await execute_memory(name, arguments)

        return await execute_browser(name, arguments)

    return browser_tools + memory_tools, execute
