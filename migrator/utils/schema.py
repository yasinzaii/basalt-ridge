from copy import deepcopy
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker, ValidationError


SCHEMA_DIR = Path(__file__).resolve().parents[1] / "stages" / "schemas"


def load_schema(name: str) -> dict:
    path = SCHEMA_DIR / f"{name}.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _allows_null(schema: dict) -> bool:
    return Draft202012Validator(schema).is_valid(None)


def model_schema(source: dict) -> dict:
    """Adapt a destination schema for strict LLM output."""
    if any(key in source for key in ("$ref", "$defs", "allOf", "oneOf", "not", "if")):
        raise ValueError("Unsupported schema construct")

    result = deepcopy(source)
    result.pop("$schema", None)
    result.pop("default", None)

    if "properties" in source:
        properties = {}
        for name, field in source["properties"].items():
            adapted = model_schema(field)

            if name not in source.get("required", []) and not _allows_null(field):
                adapted = {"anyOf": [adapted, {"type": "null"}]}

            properties[name] = adapted

        result.update(
            properties=properties,
            required=list(properties),
            additionalProperties=False,
        )

    if "items" in source:
        result["items"] = model_schema(source["items"])

    if "anyOf" in source:
        result["anyOf"] = [model_schema(branch) for branch in source["anyOf"]]

    return result


def validate(schema: dict, value, label: str) -> None:
    try:
        Draft202012Validator(
            schema,
            format_checker=FormatChecker(),
        ).validate(value)
    except ValidationError as exc:
        raise ValueError(
            f"{label}: invalid value at {exc.json_path}: {exc.message}"
        ) from None
