import json
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from migrator.agent.loop import run_agent
from migrator.tools.registry import create_tools
from migrator.utils.schema import load_schema, model_schema, validate


KINDS = ("practice", "team", "locations", "services", "payers")


def practice_output_schema() -> dict:
    nullable_id = {"anyOf": [{"type": "string", "minLength": 1}, {"type": "null"}]}
    source_refs = {
        "type": "object",
        "properties": {"url": nullable_id},
        "required": ["url"],
        "additionalProperties": False,
    }
    properties = {
        "practice": model_schema(load_schema("practice")),
        "team": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "sourceId": nullable_id,
                    "teamMember": model_schema(load_schema("team")["items"]),
                    "sourceRefs": {
                        "type": "object",
                        "properties": {"url": nullable_id, "practitionerId": nullable_id},
                        "required": ["url", "practitionerId"],
                        "additionalProperties": False,
                    },
                },
                "required": ["sourceId", "teamMember", "sourceRefs"],
                "additionalProperties": False,
            },
        },
        "locations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "sourceId": nullable_id,
                    "location": model_schema(load_schema("locations")["items"]),
                    "sourceRefs": source_refs,
                },
                "required": ["sourceId", "location", "sourceRefs"],
                "additionalProperties": False,
            },
        },
        "services": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "sourceId": nullable_id,
                    "service": model_schema(load_schema("services")["items"]),
                    "sourceRefs": source_refs,
                },
                "required": ["sourceId", "service", "sourceRefs"],
                "additionalProperties": False,
            },
        },
        "payers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "sourceId": nullable_id,
                    "payer": model_schema(load_schema("payers")["items"]),
                    "sourceRefs": source_refs,
                },
                "required": ["sourceId", "payer", "sourceRefs"],
                "additionalProperties": False,
            },
        },
        "limitations": {"type": "array", "items": {"type": "string"}},
    }
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def prepare_payloads(result: dict) -> tuple[dict, list[str]]:
    validate(practice_output_schema(), result, "Extraction")

    data = {kind: result[kind] for kind in KINDS}
    for kind in KINDS[1:]:
        ids = [record["sourceId"] for record in data[kind] if record["sourceId"] is not None]
        if len(ids) != len(set(ids)):
            raise ValueError(f"Duplicate source IDs in {kind}")
    if not any(data["practice"].values()) and not any(data[kind] for kind in KINDS[1:]):
        if not any(item.strip() for item in result["limitations"]):
            raise ValueError("No practice data extracted and no explanation provided")

    if timezone := data["practice"].get("timezone"):
        try:
            ZoneInfo(timezone)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Invalid practice timezone") from None

    return data, result["limitations"]


async def run_practice(
    backend,
    browser,
    playbook_path: Path,
    *,
    memory_directory: Path,
) -> dict:
    browser.check_page()

    playbook = playbook_path.read_text(encoding="utf-8").strip()
    if not playbook:
        raise ValueError("Practice playbook must contain navigation steps")

    messages = [
        {
            "role": "system",
            "content": (
                "Extract practice, team, locations, services and payers following the playbook. "
                "Return Carepatron fields inside each resource wrapper, with observed sourceId "
                "and sourceRefs alongside it. For team records preserve the source user ID as "
                "sourceId and any explicitly associated practitioner ID in sourceRefs.practitionerId. "
                "Never assume user and practitioner IDs are the same. Preserve verified detail URLs "
                "as sourceRefs.url; use null for unavailable IDs or URLs and report them. "
                "Never invent values or use unverified defaults. "
                "Use null for unknown optional fields; these are extraction records, not API payloads. "
                "Omit records missing required extraction fields and report them in limitations. "
                "Never modify the source. "
                "Only save browser results when they contain information worth remembering. "
                "Old browser refs are not actionable. "
                "In each tool-call summary, retain verified facts from the previous page and the next action. "
                "During tool calls, do not draft the final JSON. "
                "If a snapshot is truncated, inspect next_offset rather than repeating it. "
                "Visit every playbook section before finishing. "
                "If a section is inaccessible, record why and continue with the others. "
                "Return the final JSON only after all sections have been attempted. "
                "Start with browser_observe.\n\n"
                + playbook
            ),
        },
        {
            "role": "user",
            "content": "Extract the five practice datasets.",
        },
    ]

    
    tools, execute = create_tools(
        browser,
        allowed_actions={"click"},
        memory_directory=memory_directory,
    )

    return await run_agent(
        backend,
        messages,
        tools,
        execute,
        practice_output_schema(),
        max_turns=55,
    )



def save_practice(result: dict, directory: Path) -> dict:
    data, limitations = prepare_payloads(result)

    report = {
        "limitations": limitations,
        "missing_practice_fields": [
            key
            for key, value in result["practice"].items()
            if value is None
        ],
        "counts": {
            name: len(data[name])
            for name in KINDS[1:]
        },
        "owner_indices": [
            index
            for index, member in enumerate(data["team"])
            if member["teamMember"].get("role") == "owner"
        ],
        "owner_action": (
            "Map to the existing destination owner; do not POST an owner."
        ),
    }

    directory.mkdir(parents=True, exist_ok=False)
    (directory / "schemas").mkdir()

    for name, value in {**data, "report": report}.items():
        (directory / f"{name}.json").write_text(
            json.dumps(
                value,
                indent=2,
                ensure_ascii=False,
                allow_nan=False,
            ) + "\n",
            encoding="utf-8",
        )

    for name in KINDS:
        (directory / "schemas" / f"{name}.schema.json").write_text(
            json.dumps(load_schema(name), indent=2) + "\n",
            encoding="utf-8",
        )

    return report
