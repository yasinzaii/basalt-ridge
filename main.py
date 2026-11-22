import argparse
import asyncio
import sys
from pathlib import Path
from datetime import datetime

from playwright.async_api import Error as PlaywrightError

from migrator.agent.loop import TurnLimitExceeded
from migrator.browser.auth import AuthenticationError, wait_for_login
from migrator.browser.session import open_browser
from migrator.llm.config import ModelConfig
from migrator.llm.model import ModelError, connect_model
from migrator.stages.practice import run_practice, save_practice

LOGIN_URL = "https://www.cliniko.com/login/"
PLAYBOOK = Path(__file__).resolve().parent / "migrator/playbooks/cliniko/practice.md"
OUTPUT = Path(__file__).resolve().parent / "artifacts/practice"
MEMORY_ROOT = Path(__file__).resolve().parent / "artifacts/memory"


async def run(playbook: Path = PLAYBOOK, output: Path = OUTPUT) -> None:
    if output.exists():
        raise FileExistsError("Choose a new output directory with --output")
    if not playbook.read_text(encoding="utf-8").strip():
        raise ValueError("Provide a nonempty playbook")
    memory_directory = MEMORY_ROOT / datetime.now().astimezone().strftime(
        "%Y-%m-%d_%H-%M-%S_%f"
    )
    async with open_browser(LOGIN_URL) as browser:
        await wait_for_login(browser)
        print("Practice extraction started. Leave the browser untouched.", file=sys.stderr)
        async with connect_model(ModelConfig.from_env()) as backend:
            result = await run_practice(backend, browser, playbook, memory_directory=memory_directory)
    report = save_practice(result, output)
    print(f"Saved five JSON files and schemas to {output}")
    for item in report["limitations"]:
        print(f"Limitation: {item}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--playbook", type=Path, default=PLAYBOOK)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    try:
        asyncio.run(run(args.playbook, args.output))
        return 0
    except (AuthenticationError, PlaywrightError):
        print("Browser or login failed.", file=sys.stderr)
        return 1
    except (ModelError, TurnLimitExceeded, ValueError, OSError) as exc:
        print(f"Practice extraction failed: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
