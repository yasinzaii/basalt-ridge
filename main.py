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
from migrator.stages.clients import run_clients, save_clients


ROOT = Path(__file__).resolve().parent
LOGIN_URL = "https://www.cliniko.com/login/"
STAGES = {"clients": (run_clients, save_clients)}


async def run(stage: str = "clients", playbook: Path | None = None, output: Path | None = None) -> None:
    run_stage, save_stage = STAGES[stage]
    playbook = playbook or ROOT / f"migrator/playbooks/cliniko/{stage}.md"
    stamp = datetime.now().astimezone().strftime("%Y-%m-%d_%H-%M-%S_%f")
    output = output or ROOT / "artifacts" / stage / stamp
    if output.exists():
        raise FileExistsError("Choose a new output directory with --output")
    if not playbook.read_text(encoding="utf-8").strip():
        raise ValueError("Provide a nonempty playbook")
    memory_directory = ROOT / "artifacts/memory" / stage / stamp

    async with open_browser(LOGIN_URL) as browser:
        await wait_for_login(browser)
        print(f"{stage.title()} extraction started. Leave the browser untouched.", file=sys.stderr)
        async with connect_model(ModelConfig.from_env()) as backend:
            result = await run_stage(backend, browser, playbook, memory_directory=memory_directory)

    report = save_stage(result, output)
    print(f"Saved {stage} extraction to {output}")
    for item in report["limitations"]:
        print(f"Limitation: {item}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=STAGES, default="clients")
    parser.add_argument("--playbook", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        asyncio.run(run(args.stage, args.playbook, args.output))
        return 0
    except (AuthenticationError, PlaywrightError):
        print("Browser or login failed.", file=sys.stderr)
        return 1
    except (ModelError, TurnLimitExceeded, ValueError, OSError) as exc:
        print(f"Extraction failed: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
