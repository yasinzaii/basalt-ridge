import json
from copy import deepcopy

from playwright.async_api import Error as PlaywrightError

from migrator.browser.session import ACTIONS, BrowserActionError, BrowserSession


BROWSER_TOOLS = [
    {"type": "function", "function": {
        "name": "browser_observe", "description": "Return the current Playwright AI snapshot with actionable refs.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "summary": {"type": "string", "minLength": 1, "maxLength": 240,
                            "description": "Describe the intended observation and its purpose; not proof of its outcome."},
            },
            "required": ["summary"], "additionalProperties": False,
        },
    }},
    {"type": "function", "function": {
        "name": "browser_action",
        "description": "Act on a current authenticated-page snapshot ref. Use value=null for click/check/uncheck. Returns an updated snapshot. The operator completes login before discovery starts.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": sorted(ACTIONS)},
                "ref": {"type": "string"},
                "value": {"type": ["string", "null"]},
                "summary": {"type": "string", "minLength": 1, "maxLength": 240,
                            "description": "Describe the intended action, target and purpose; not proof of its outcome."},
            },
            "required": ["action", "ref", "value", "summary"], "additionalProperties": False,
        },
    }},
]


def create_browser_tools(browser: BrowserSession, *, allowed_actions=None):
    """Build matching schemas and dispatch from the same permitted actions."""
    permitted = ACTIONS if allowed_actions is None else frozenset(allowed_actions)
    if not permitted or not permitted <= ACTIONS:
        raise ValueError("Choose at least one supported browser action")
    tools = deepcopy(BROWSER_TOOLS)
    properties = tools[1]["function"]["parameters"]["properties"]
    properties["action"]["enum"] = sorted(permitted)


    async def execute(name: str, arguments: dict) -> str:
        try:
            if name == "browser_observe":
                result = await browser.observe()
            elif name == "browser_action":
                if arguments["action"] not in permitted:
                    raise BrowserActionError("This action is not permitted in the current stage")
                result = await browser.action(**arguments)
            else:
                raise ValueError("Unknown browser tool")
            return json.dumps(result)
        except BrowserActionError as exc:
            return json.dumps({"error": "BrowserActionError", "message": str(exc)})
        except PlaywrightError:
            browser.invalidate_refs()
            return json.dumps({"error": "BrowserOperationError", "message": "Action or observation failed; its result may be uncertain. Observe before retrying. Do not blindly repeat a submission."})
    return tools, execute
