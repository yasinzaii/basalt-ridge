"""Save exact browser results as JSON; expose retrieval by file ID."""

import json
from pathlib import Path
import re
from uuid import uuid4

from migrator.utils.files import read_json


MEMORY_TOOLS = [
    {"type": "function", "function": {
        "name": "memory_load",
        "description": "Load a saved browser result by its memory_id. Old refs are evidence, not current controls.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "pattern": "^[a-f0-9]{32}$"},
            },
            "required": ["id"], "additionalProperties": False,
        },
    }},
]


def save_record(directory: Path, result: dict) -> str:
    record_id = uuid4().hex
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{record_id}.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8",
    )
    return record_id


def create_memory_tools(directory: Path):
    directory = directory.resolve()

    async def execute(name: str, arguments: dict) -> str:
        if name != "memory_load":
            raise ValueError("Unknown memory tool")
        try:
            record_id = arguments["id"]
            if not re.fullmatch(r"[a-f0-9]{32}", record_id):
                raise ValueError("Invalid memory ID")
            path = (directory / f"{record_id}.json").resolve()
            if not path.is_relative_to(directory):
                raise ValueError("Memory ID must stay within its directory")
            return json.dumps({"id": record_id, "content": read_json(path)},
                              ensure_ascii=False, allow_nan=False)
        except (OSError, ValueError) as exc:
            return json.dumps({"error": type(exc).__name__, "message": "Could not load that memory ID."})

    return MEMORY_TOOLS, execute
