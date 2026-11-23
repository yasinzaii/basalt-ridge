"""Append and load stage records from one JSON list."""

import json
from pathlib import Path

from migrator.utils.files import read_json, write_json


STAGE_RECORD_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "append_record",
            "description": "Append one record to this stage's JSON list. Supply a JSON object encoded as text.",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {"record": {"type": "string", "description": "One JSON object as text."}},
                "required": ["record"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "load_records",
            "description": "Load the current stage's saved records, or the completed JSON records from a previous stage in this run.",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "stage": {
                        "type": "string",
                        "enum": ["current", "practice", "clients", "appointments", "notes"],
                        "description": "Use current for this stage's list, or name a completed stage.",
                    },
                },
                "required": ["stage"],
                "additionalProperties": False,
            },
        },
    },
]


def create_stage_record_tools(directory: Path):
    path = directory / "records.json"

    async def execute(name: str, arguments: dict) -> str:
        if name == "load_records":
            stage = arguments["stage"]
            if stage == "current":
                records = read_json(path) if path.exists() else []
            elif stage in {"practice", "clients", "appointments", "notes"}:
                run_directory = directory.resolve().parent.parent
                stage_directory = (run_directory / stage).resolve()
                if not stage_directory.is_relative_to(run_directory) or not stage_directory.is_dir():
                    return json.dumps({"error": "Stage records are not available in this run"})
                records = {
                    file.stem: read_json(file)
                    for file in stage_directory.glob("*.json")
                    if file.name != "report.json" and file.resolve().is_relative_to(stage_directory)
                }
            else:
                return json.dumps({"error": "Unknown stage"})
            return json.dumps(records, ensure_ascii=False, allow_nan=False)
        records = read_json(path) if path.exists() else []
        if name != "append_record":
            raise ValueError("Unknown stage record tool")
        try:
            record = json.loads(arguments["record"])
            if not isinstance(record, dict):
                raise ValueError("Record must be a JSON object")
            json.dumps(record, allow_nan=False)
        except (ValueError, TypeError):
            return json.dumps({"error": "Provide one valid JSON object as record"})
        records.append(record)
        directory.mkdir(parents=True, exist_ok=True)
        write_json(path, records)
        return json.dumps({"saved": True, "count": len(records)})

    return STAGE_RECORD_TOOLS, execute
