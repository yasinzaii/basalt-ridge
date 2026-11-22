"""Workspace file listing and UTF-8 reading tools with model-facing schemas."""

import csv
from itertools import islice
import json
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[2] / "workspace"
MAX_FILE_BYTES = 100_000

LIST_FILES_SCHEMA = {
    "type": "function",
    "function": {
        "name": "list_files",
        "description": "Recursively list files in a workspace directory, returning sorted workspace-relative paths as JSON.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative directory path; use . for the workspace root."},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
    },
}

READ_FILE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Read a UTF-8 text file up to 100,000 bytes from the configured download folder.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative file path, for example example.txt."},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
    },
}

READ_CSV_SCHEMA = {
    "type": "function",
    "function": {
        "name": "read_csv",
        "description": "Read CSV headers and up to 50 rows. Start at offset 0, then follow next_offset until null. Values remain strings; quoted newlines and leading zeros are preserved.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path returned by browser_download."},
                "offset": {"type": "integer", "minimum": 0},
            },
            "required": ["path", "offset"],
            "additionalProperties": False,
        },
    },
}


def list_files(path: str = ".", *, directory: Path = WORKSPACE) -> str:
    root = directory.resolve()
    relative = Path(path)
    target = (root / relative).resolve()
    if relative.is_absolute() or not target.is_relative_to(root):
        raise ValueError("Use a relative path inside the workspace")
    if not target.is_dir():
        raise NotADirectoryError("Requested workspace directory does not exist or is not a directory")
    paths = sorted(
        file.relative_to(root).as_posix()
        for file in target.rglob("*")
        if file.is_file() and file.resolve().is_relative_to(root)
    )
    return json.dumps(paths)


def read_file(path: str, *, directory: Path = WORKSPACE) -> str:
    root = directory.resolve()
    relative = Path(path)
    target = (root / relative).resolve()
    if relative.is_absolute() or not target.is_relative_to(root):
        raise ValueError("Use a relative path inside the workspace")
    with target.open("rb") as file:
        content = file.read(MAX_FILE_BYTES + 1)
    if len(content) > MAX_FILE_BYTES:
        raise ValueError("File exceeds the read limit")
    return content.decode("utf-8-sig")


def read_csv(path: str, offset: int, *, directory: Path) -> str:
    root = directory.resolve()
    target = (root / path).resolve()
    if Path(path).is_absolute() or not target.is_relative_to(root):
        raise ValueError("Use a relative path inside the download folder")
    if offset < 0:
        raise ValueError("Offset must be nonnegative")
    with target.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.reader(file)
        headers = next(reader, None)
        if not headers:
            raise ValueError("CSV has no headers")
        rows = list(islice(reader, offset, offset + 51))
    if any(len(row) != len(headers) for row in rows):
        raise ValueError("CSV row does not match its headers")
    return json.dumps({
        "headers": headers,
        "rows": rows[:50],
        "offset": offset,
        "next_offset": offset + 50 if len(rows) > 50 else None,
    }, ensure_ascii=False)


def create_file_tools(directory: Path):
    async def execute(name: str, arguments: dict) -> str:
        functions = {"list_files": list_files, "read_file": read_file, "read_csv": read_csv}
        if name not in functions:
            raise ValueError("Unknown file tool")
        return functions[name](**arguments, directory=directory)

    return [LIST_FILES_SCHEMA, READ_FILE_SCHEMA, READ_CSV_SCHEMA], execute
