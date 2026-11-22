from datetime import datetime, timezone

from migrator.utils.schema import load_schema, validate


def non_null(record: dict) -> dict:
    """Return the fields whose values are not None."""
    return {key: value for key, value in record.items() if value is not None}


def check_payload(kind: str, payload: dict) -> None:
    validate(load_schema(kind), [payload], f"{kind} API payload")


def _instant(value):
    """Parse a timestamp only when it has an explicit timezone."""
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def matches_submitted_fields(field: str, expected, actual) -> bool:
    """Compare submitted values; allow extra fields in response objects."""
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            key in actual and matches_submitted_fields(key, value, actual[key])
            for key, value in expected.items()
        )
    if isinstance(expected, list):
        return isinstance(actual, list) and len(expected) == len(actual) and all(
            matches_submitted_fields(field, left, right)
            for left, right in zip(expected, actual)
        )
    if field in ("startsAt", "endsAt", "createdAt", "signedAt") and expected is not None:
        expected_instant = _instant(expected)
        return expected_instant is not None and expected_instant == _instant(actual)
    if isinstance(expected, bool) or isinstance(actual, bool):
        return type(expected) is type(actual) and expected == actual
    return expected == actual
