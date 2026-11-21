import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from migrator.agent.loop import run_agent
from migrator.browser.session import BrowserSession
from migrator.llm.model import ModelBackend
from migrator.tools.browser import create_browser_tools


class DiscoveryReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str
    practice_structure: list[str]
    export_options: list[str]
    limitations: list[str]


async def run_discovery(backend: ModelBackend, browser: BrowserSession, login: dict) -> DiscoveryReport:
    if login.get("status") != "operator_confirmed":
        raise ValueError("Discovery requires an operator-confirmed handoff")
    browser.check_page()
    playbook = (Path(__file__).resolve().parents[1] / "playbooks" / "cliniko" / "discovery.md").read_text(encoding="utf-8")
    messages = [
        {"role": "system", "content": (
            "You are a practice discovery agent. The operator has confirmed login. "
            "Do not log in again or request credentials. First use browser_observe. "
            "Inspect practice structure and available export options using navigation only. "
            "Include a nonblank summary of at most 240 characters with every tool call: "
            "the intended action, target and purpose. Only claim earlier outcomes "
            "confirmed by observations. "
            "Return a concise structured report.\n\n" + playbook
        )},
        {"role": "user", "content": "Operator handoff: " + json.dumps(login) +
         "\nDiscover the practice structure and available patient-data export options."},
    ]
    tools, execute_tool = create_browser_tools(browser, allowed_actions={"click"})
    report = await run_agent(
        backend, messages, tools, execute_tool,
        DiscoveryReport, max_turns=30,
    )
    browser.check_page()
    return report
