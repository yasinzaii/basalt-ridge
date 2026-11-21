"""Workspace file listing and UTF-8 reading tools with model-facing schemas."""

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
        "description": "Read a UTF-8 text file up to 100,000 bytes from the fixed workspace folder.",
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


def list_files(path: str = ".") -> str:
    root = WORKSPACE.resolve()
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


def read_file(path: str) -> str:
    root = WORKSPACE.resolve()
    relative = Path(path)
    target = (root / relative).resolve()
    if relative.is_absolute() or not target.is_relative_to(root):
        raise ValueError("Use a relative path inside the workspace")
    with target.open("rb") as file:
        content = file.read(MAX_FILE_BYTES + 1)
    if len(content) > MAX_FILE_BYTES:
        raise ValueError("File exceeds the read limit")
    return content.decode("utf-8")
