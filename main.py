import argparse
import asyncio
import json
import sys

from playwright.async_api import Error as PlaywrightError

from migrator.agent.loop import TurnLimitExceeded
from migrator.stages.discovery import run_discovery
from migrator.browser.auth import AuthenticationError, wait_for_login
from migrator.browser.session import open_browser
from migrator.llm.config import ModelConfig
from migrator.llm.model import ModelError, connect_model



LOGIN_URL = "https://www.cliniko.com/login/"


async def run() -> int:
    async with open_browser(LOGIN_URL) as browser:
        login = await wait_for_login(browser)
        print("Starting AI discovery; please leave the browser untouched. Ctrl+C stops the run.", file=sys.stderr)
        # No model client or model request exists during manual authentication.
        config = ModelConfig.from_env()
        async with connect_model(config) as backend:
            report = await run_discovery(backend, browser, login)
        print(json.dumps({"login": login, "discovery": report.model_dump()}, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    try:
        return asyncio.run(run())
    except AuthenticationError as exc:
        print(str(exc), file=sys.stderr)
    except PlaywrightError:
        print("Browser operation failed. Check Chromium and connectivity. Raw browser errors are suppressed.", file=sys.stderr)
    except (ValueError, ModelError, TurnLimitExceeded, OSError):
        print("Could not finish. Check the URL in main.py, model configuration and playbook access.", file=sys.stderr)
    except KeyboardInterrupt:
        print("Run stopped.", file=sys.stderr)
        return 130
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
