import argparse
import asyncio
import sys

from pydantic import BaseModel, ConfigDict

from migrator.agent.loop import TurnLimitExceeded, run_agent
from migrator.llm.config import ModelConfig
from migrator.llm.model import ModelError, connect_model
from migrator.tools.registry import TOOLS, execute_tool


class FileReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str
    files_reviewed: list[str]
    findings: list[str]
    limitations: list[str]


async def run(instruction: str) -> None:
    config = ModelConfig.from_env()
    messages = [
        {
            "role": "system",
            "content": (
                "You are a read-only project analysis agent. "
                "First use list_files with path '.' to discover the workspace files. "
                "Then use read_file to inspect each listed file. "
                "Report your findings and identify any files you could not inspect. "
            ),
        },
        {"role": "user", "content": instruction},
    ]
    async with connect_model(config) as backend:
        report = await run_agent(
            backend, messages, TOOLS, execute_tool, FileReport, max_turns=50,
        )
    print(report.model_dump_json(indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("instruction", nargs="?", help="Instruction for reviewing workspace files")
    args = parser.parse_args()
    try:
        instruction = args.instruction if args.instruction is not None else input("Instruction: ")
        if not instruction.strip():
            parser.error("instruction must not be blank")
        asyncio.run(run(instruction.strip()))
    except EOFError:
        parser.error("provide an instruction as an argument or through the interactive prompt")
    except (ValueError, ModelError, TurnLimitExceeded) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
