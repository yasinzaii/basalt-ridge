import asyncio
import json
import os
from pathlib import Path

from migrator.agent.loop import run_agent
from migrator.tools.registry import create_tools

from .session import BrowserSession


class AuthenticationError(RuntimeError):
    pass


async def wait_for_login(browser: BrowserSession) -> None:
    browser.invalidate_refs()
    try:
        await asyncio.to_thread(input, "Complete login in the browser, then press Enter here to start extraction: ")
    except EOFError:
        raise AuthenticationError("Login handoff requires an interactive terminal") from None
    browser.check_page()


async def login(backend, browser: BrowserSession, source: str, playbook: Path, *, memory_directory: Path) -> None:
    prefix = source.upper() + "_"
    settings = {key: value for key, value in os.environ.items() if key.upper().startswith(prefix)}
    if not settings:
        raise AuthenticationError(f"Set {prefix} environment variables before starting login")

    messages = [
        {"role": "system", "content": playbook.read_text(encoding="utf-8")},
        {"role": "user", "content": "Sign in using these source settings: " + json.dumps(settings)},
    ]
    tools, execute = create_tools(browser, memory_directory=memory_directory,
                                  allowed_actions={"click", "fill", "press"})
    schema = {
        "type": "object",
        "properties": {"status": {"type": "string", "enum": ["logged_in", "blocked"]}},
        "required": ["status"], "additionalProperties": False,
    }
    result = await run_agent(backend, messages, tools, execute, schema, max_turns=20)
    if result["status"] != "logged_in":
        raise AuthenticationError(f"{source} login was blocked")
    browser.check_page()
    browser.invalidate_refs()
