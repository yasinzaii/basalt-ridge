import json
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from migrator.agent.loop import run_agent
from migrator.tools.registry import create_tools
from migrator.utils.schema import load_schema, model_schema, validate


KINDS = ("practice", "team", "locations", "services", "payers")


def practice_output_schema() -> dict:
    properties = {
        name: model_schema(load_schema(name))
        for name in KINDS
    }
    properties["limitations"] = {
        "type": "array",
        "items": {"type": "string"},
    }

    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def prepare_payloads(result: dict) -> tuple[dict, list[str]]:
    validate(practice_output_schema(), result, "Extraction")

    data = {
        "practice": {
            key: value
            for key, value in result["practice"].items()
            if value is not None
        },
        **{name: result[name] for name in KINDS[1:]},
    }

    for service in data["services"]:
        if service.get("modifiers") is None:
            service.pop("modifiers", None)

    if not any(data.values()):
        raise ValueError("No practice data was extracted")

    for name, payload in data.items():
        validate(load_schema(name), payload, name)

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
                "Return exact Carepatron API fields without destination IDs. "
                "Never invent values or use unverified defaults. "
                "For unknown practice fields use null. For other records, use null only "
                "where the API permits it; omit incomplete records and report them in limitations. "
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
            if member.get("role") == "owner"
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
