"""Schemas and dispatch for workspace file tools."""

import json

from .files import LIST_FILES_SCHEMA, READ_FILE_SCHEMA, list_files, read_file


TOOLS = [READ_FILE_SCHEMA, LIST_FILES_SCHEMA]


async def execute_tool(name: str, arguments: dict) -> str:
    # run_agent validates arguments against TOOLS before dispatching.
    if name == "list_files":
        try:
            return list_files(**arguments)
        except (OSError, ValueError) as exc:
            return json.dumps({"error": type(exc).__name__, "message": "Could not list the requested workspace directory; check the relative directory path."})
    if name == "read_file":
        try:
            return read_file(**arguments)
        except (OSError, UnicodeError, ValueError) as exc:
            return json.dumps({"error": type(exc).__name__, "message": "Could not read the requested workspace text file; check the path, UTF-8 encoding, and 100,000-byte limit."})
    raise ValueError("Unknown tool")
