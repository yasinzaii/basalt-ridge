import asyncio
import json
import traceback
from datetime import datetime
from copy import deepcopy
from pathlib import Path

from .memory import save_record

from playwright.async_api import Error as PlaywrightError

from migrator.browser.session import ACTIONS, BrowserActionError, BrowserSession


BROWSER_TOOLS = [
    {"type": "function", "function": {
        "name": "browser_observe", "description": "Return the current Playwright AI snapshot with actionable refs.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "save_result": {"type": "boolean",
                                "description": "Save this exact result to JSON and return its memory_id when true."},
                "offset": {"type": "integer", "minimum": 0,
                           "description": "Snapshot character offset: 0 initially, then use next_offset when truncated."},
                "summary": {"type": "string", "minLength": 1, "maxLength": 240,
                            "description": "Summarize verified findings from the previous observation and the next intended step."},
            },
            "required": ["summary", "save_result", "offset"], "additionalProperties": False,
        },
    }},
    {"type": "function", "function": {
        "name": "browser_action",
        "description": "Act on a current authenticated-page snapshot ref. Use value=null for click/check/uncheck. Returns an updated snapshot. Never click disabled controls or repeat a failed action without a relevant state change. For popup controls, open the associated input first and use the enabled control in the returned snapshot. The operator completes login before the agent starts.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "save_result": {"type": "boolean",
                                "description": "Save this exact result to JSON and return its memory_id when true."},
                "action": {"type": "string", "enum": sorted(ACTIONS)},
                "ref": {"type": "string"},
                "value": {"type": ["string", "null"]},
                "summary": {"type": "string", "minLength": 1, "maxLength": 240,
                            "description": "Summarize verified findings from the previous observation and the next intended action."},
            },
            "required": ["action", "ref", "value", "summary", "save_result"], "additionalProperties": False,
        },
    }},
    {"type": "function", "function": {
        "name": "browser_wait",
        "description": "Wait for asynchronous page updates, then return a fresh browser snapshot. Waiting does not guarantee the task is complete; inspect the result.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "seconds": {"type": "integer", "minimum": 1, "maximum": 10},
                "summary": {"type": "string", "minLength": 1, "maxLength": 240},
            },
            "required": ["seconds", "summary"], "additionalProperties": False,
        },
    }},
]


DOWNLOAD_TOOL = {"type": "function", "function": {
    "name": "browser_download",
    "description": "Click a current CSV download ref, wait for completion and save locally. Use read_csv with the returned path. Use this instead of browser_action for download links.",
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "ref": {"type": "string"},
            "save_result": {"type": "boolean"},
            "summary": {"type": "string", "minLength": 1, "maxLength": 240},
        },
        "required": ["ref", "save_result", "summary"],
        "additionalProperties": False,
    },
}}


def create_browser_tools(browser: BrowserSession, *, memory_directory: Path, allowed_actions=None,
                         download_directory: Path | None = None):
    """Build matching schemas and dispatch from the same permitted actions."""
    permitted = ACTIONS if allowed_actions is None else frozenset(allowed_actions)
    if not permitted or not permitted <= ACTIONS:
        raise ValueError("Choose at least one supported browser action")
    tools = deepcopy(BROWSER_TOOLS)
    if download_directory is not None:
        tools.append(deepcopy(DOWNLOAD_TOOL))
    properties = tools[1]["function"]["parameters"]["properties"]
    properties["action"]["enum"] = sorted(permitted)


    async def execute(name: str, arguments: dict) -> str:
        arguments = arguments.copy()
        save_result = arguments.pop("save_result", False)
        try:
            if name == "browser_observe":
                result = await browser.observe(offset=arguments["offset"])
            elif name == "browser_wait":
                await asyncio.sleep(arguments["seconds"])
                result = await browser.observe()
            elif name == "browser_download" and download_directory is not None:
                result = await browser.download(arguments["ref"], download_directory)
            elif name == "browser_action":
                if arguments["action"] not in permitted:
                    raise BrowserActionError("This action is not permitted in the current stage")
                result = await browser.action(**arguments)
            else:
                raise ValueError("Unknown browser tool")
            if save_result:
                record_id = save_record(memory_directory, result)
                result = {**result, "memory_id": record_id}
            return json.dumps(result)
        except BrowserActionError as exc:
            return json.dumps({"error": "BrowserActionError", "message": str(exc)})
        except PlaywrightError:
            browser.invalidate_refs()
            memory_directory.mkdir(parents=True, exist_ok=True)
            with (memory_directory / "browser-errors.log").open("a", encoding="utf-8") as log:
                log.write(f"\n{datetime.now().astimezone().isoformat()} {name}\n")
                log.write(traceback.format_exc())
            return json.dumps({"error": "BrowserOperationError", "message": "Action or observation failed; its result may be uncertain. Observe before retrying. Do not blindly repeat a submission."})
    return tools, execute
