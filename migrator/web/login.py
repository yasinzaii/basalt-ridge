import json

from migrator.agent.loop import run_agent
from migrator.browser.session import BrowserActionError
from migrator.tools.registry import create_tools
from playwright.async_api import Error as PlaywrightError


INPUT_TOOL = {
    "type": "function",
    "function": {
        "name": "request_input",
        "description": "Ask the user for a login field and fill the current page ref. Observe again after filling.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "ref": {"type": "string", "description": "Input reference from the current snapshot."},
                "label": {"type": "string", "description": "Short label to show the user."},
                "kind": {"type": "string", "enum": ["text", "password"]},
            },
            "required": ["ref", "label", "kind"],
            "additionalProperties": False,
        },
    },
}

MANUAL_TOOL = {
    "type": "function",
    "function": {
        "name": "request_manual_step",
        "description": "Ask the user to complete a step in the visible browser, then observe again.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
            "additionalProperties": False,
        },
    },
}


async def interactive_login(backend, browser, source, memory_directory, ask):
    tools, browser_execute = create_tools(
        browser, memory_directory=memory_directory, allowed_actions={"click", "press"},
    )
    tools[1]["function"]["description"] = "Click or press a current login-page ref. Use request_input to fill fields."
    tools += [INPUT_TOOL, MANUAL_TOOL]

    async def execute(name, arguments):
        if name == "request_input":
            value = await ask({"kind": "input", "label": arguments["label"], "input_type": arguments["kind"]})
            try:
                await browser.action("fill", arguments["ref"], value)
            except (BrowserActionError, PlaywrightError):
                return json.dumps({"error": "Could not fill the field. Observe and try again."})
            return json.dumps({"filled": True})
        if name == "request_manual_step":
            await ask({"kind": "manual", "message": arguments["message"]})
            browser.invalidate_refs()
            return json.dumps({"continued": True})
        if "save_result" in arguments:
            arguments = {**arguments, "save_result": False}
        return await browser_execute(name, arguments)

    messages = [{"role": "system", "content": (
        f"Sign in to the user's {source} account. Observe the current page first. "
        "Use request_input for each email, password, or verification-code field using its current ref; "
        "never ask the model to supply field values. After each input, observe again. "
        "Click the appropriate sign-in or continue controls. If a CAPTCHA, passkey, or other "
        "step requires the user to interact with the visible browser, use request_manual_step. "
        "Confirm the signed-in page before reporting logged_in. Never repeat an uncertain submission."
    )}]
    schema = {"type": "object", "properties": {
        "status": {"type": "string", "enum": ["logged_in", "blocked"]},
    }, "required": ["status"], "additionalProperties": False}
    result = await run_agent(backend, messages, tools, execute, schema, max_turns=30)
    if result["status"] != "logged_in":
        raise ValueError("Login could not be completed")
    browser.invalidate_refs()
