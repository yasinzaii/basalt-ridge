import argparse
import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime

from playwright.async_api import Error as PlaywrightError

from migrator.agent.loop import TurnLimitExceeded
from migrator.browser.auth import AuthenticationError, login, wait_for_login
from migrator.browser.session import open_browser
from migrator.llm.config import ModelConfig
from migrator.llm.model import ModelError, connect_model
from migrator.stages.practice import run_practice, save_practice
from migrator.stages.clients import run_clients, save_clients
from migrator.stages.appointments import run_appointments, save_appointments
from migrator.stages.notes import run_notes, save_notes
from migrator.stages.import_api import ApiError, import_run
from migrator.utils.run_validation import validate_run
from migrator.utils.files import write_json

ROOT = Path(__file__).resolve().parent
LOGIN_URL = "https://www.cliniko.com/login/"
DEFAULT_STAGE = "all"
STAGES = {
    "practice": (run_practice, save_practice),
    "clients": (run_clients, save_clients),
    "appointments": (run_appointments, save_appointments),
    "notes": (run_notes, save_notes),
}


async def run(stage: str = DEFAULT_STAGE, output: Path | None = None,
              source: str = "cliniko") -> Path:
    if stage != "all" and stage not in STAGES:
        raise ValueError("Unknown stage")
    selected = list(STAGES) if stage == "all" else [stage]
    playbooks = {name: ROOT / f"migrator/playbooks/{source}/{name}.md" for name in selected}
    for path in playbooks.values():
        if not path.read_text(encoding="utf-8").strip():
            raise ValueError(f"Empty playbook: {path.name}")
    started = datetime.now().astimezone()
    stamp = started.strftime("%Y-%m-%d_%H-%M-%S_%f")
    output = output or ROOT / "artifacts" / source / stamp
    output.mkdir(parents=True, exist_ok=False)
    manifest = {
        "formatVersion": 2, "source": source, "runId": stamp,
        "startedAt": started.isoformat(), "status": "running",
        "identityConvention": "Record sourceId and relationship IDs are source identifiers, never destination IDs.",
        "stages": {name: {"status": "pending" if name in selected else "not_requested", "path": name}
                   for name in STAGES},
    }
    manifest["stages"]["policies"] = {"status": "not_implemented"}
    write_json(output / "manifest.json", manifest)
    active = None
    try:
        login_url = LOGIN_URL if source == "cliniko" else os.getenv(
            "ZANDA_LOGIN_URL", "https://my.zandahealth.com/Account/Login"
        )
        async with open_browser(login_url) as browser:
            async with connect_model(ModelConfig.from_env()) as backend:
                print(f"\n--- {source.title()} login started ---\n", flush=True)
                if source == "cliniko":
                    await wait_for_login(browser)
                else:
                    await login(backend, browser, source, ROOT / f"migrator/playbooks/{source}/login.md",
                                memory_directory=output / "_work" / "login")
                manifest["sourceAccountUrl"] = browser.page.url
                write_json(output / "manifest.json", manifest)
                for number, name in enumerate(selected, start=1):
                    active = name
                    state = manifest["stages"][name]
                    state["status"] = "running"
                    write_json(output / "manifest.json", manifest)
                    browser.invalidate_refs()
                    print(f"\n--- Stage {number}/{len(selected)}: {name.title()} extraction started ---\n", flush=True)
                    run_stage, save_stage = STAGES[name]
                    result = await run_stage(backend, browser, playbooks[name],
                                             memory_directory=output / "_work" / name)
                    report = save_stage(result, output / name)
                    state.update(status="completed", limitations=report["limitations"])
                    write_json(output / "manifest.json", manifest)
                    print(f"\n{name.title()} extraction completed.", flush=True)
                    if report["limitations"]:
                        print("\nLimitations:", flush=True)
                        for item in report["limitations"]:
                            print(f"  - {item}\n", flush=True)
                    active = None
        validation = validate_run(output, manifest)
        write_json(output / "validation.json", validation)
        manifest["status"] = "completed_with_limitations" if validation["status"] != "passed" else "completed"
    except BaseException as exc:
        manifest["status"] = "incomplete"
        manifest["error"] = type(exc).__name__
        if active is not None:
            manifest["stages"][active]["status"] = "failed"
            print(f"\n{active.title()} extraction failed.", flush=True)
        raise
    finally:
        manifest["finishedAt"] = datetime.now().astimezone().isoformat()
        write_json(output / "manifest.json", manifest)
        print(f"\nExtraction run saved to {output} ({manifest['status']})\n", flush=True)


    return output


def run_import(directory: Path, api_url: str) -> None:
    print("\n--- Import stage started ---\n", flush=True)
    report = import_run(directory, api_url)
    print("\nImport completed.", flush=True)
    if report["warnings"]:
        print("\nImport limitations:", flush=True)
        for item in report["warnings"]:
            print(f"  - {item}\n", flush=True)
    print(f"Report saved to {directory / 'import' / 'report.json'}\n", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=["cliniko", "zanda"], default="cliniko")
    parser.add_argument("--stage", choices=["all", *STAGES, "import"], default="import")
    parser.add_argument("--output", type=Path, help="New run directory; must not exist")
    parser.add_argument("--run-dir", type=Path, help="Previous completed extraction directory")
    parser.add_argument("--api-url", default="http://127.0.0.1:4000/api/v1")
    args = parser.parse_args()
    try:
        if args.stage == "import":
            if args.run_dir is None:
                raise ValueError("Provide --run-dir for the import stage")
            run_import(args.run_dir, args.api_url)
            return 0
        run_directory = asyncio.run(run(args.stage, args.output, args.source))
        if args.stage == "all":
            run_import(run_directory, args.api_url)
        return 0
    except (AuthenticationError, PlaywrightError):
        print("Browser or login failed.", file=sys.stderr)
        return 1
    except (ModelError, TurnLimitExceeded, ApiError, ValueError, OSError) as exc:
        print(f"Migration failed: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
