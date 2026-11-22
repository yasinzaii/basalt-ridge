
from pathlib import Path

from migrator.tools.browser import create_browser_tools
from migrator.tools.memory import create_memory_tools
from migrator.tools.files import create_file_tools


def create_tools(browser, *, memory_directory: Path, allowed_actions=None,
                 download_directory: Path | None = None):
    browser_tools, execute_browser = create_browser_tools(
        browser,
        allowed_actions=allowed_actions,
        memory_directory=memory_directory,
        download_directory=download_directory,
    )

    memory_tools, execute_memory = create_memory_tools(
        memory_directory
    )

    file_tools = []
    if download_directory is not None:
        file_tools, execute_file = create_file_tools(download_directory)
    file_names = {tool["function"]["name"] for tool in file_tools}

    async def execute(name: str, arguments: dict) -> str:
        if name in file_names:
            return await execute_file(name, arguments)
        if name == "memory_load":
            browser.invalidate_refs()
            return await execute_memory(name, arguments)

        return await execute_browser(name, arguments)

    return browser_tools + memory_tools + file_tools, execute
