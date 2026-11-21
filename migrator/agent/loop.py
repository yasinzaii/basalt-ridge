from collections.abc import Awaitable, Callable
from copy import deepcopy
import json

from jsonschema import Draft202012Validator
from pydantic import BaseModel, ValidationError

from migrator.llm.model import ModelBackend, ModelError


class TurnLimitExceeded(RuntimeError):
    pass


def _json_object(text: str) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate key")
            result[key] = value
        return result

    def nonfinite(value):
        raise ValueError("Nonfinite JSON")

    try:
        value = json.loads(text, object_pairs_hook=pairs, parse_constant=nonfinite)
        if not isinstance(value, dict):
            raise ValueError("Expected object")
        json.dumps(value, allow_nan=False)  # Reject numeric overflow before tool execution.
        return value
    except (ValueError, TypeError):
        raise ModelError("Model must return a valid JSON object") from None


async def run_agent(
    backend: ModelBackend, messages: list[dict], tools: list[dict],
    execute_tool: Callable[[str, dict], Awaitable[str]], output_type: type[BaseModel],
    max_turns: int = 20,
) -> BaseModel:
    if max_turns < 1:
        raise ValueError("max_turns must be positive")
    validators = {}
    for tool in tools:
        function = tool["function"]
        if function["name"] in validators:
            raise ValueError("Duplicate tool definition")
        Draft202012Validator.check_schema(function["parameters"])
        validators[function["name"]] = Draft202012Validator(function["parameters"])
    base_history = deepcopy(messages)
    history = base_history.copy()
    seen_calls = set()
    schema = output_type.model_json_schema()
    for turn in range(max_turns):
        reply = await backend.generate(history, tools, schema)
        if reply.finish_reason == "tool_calls":
            if len(reply.tool_calls) != 1:
                raise ModelError("Expected exactly one tool call")
            call = reply.tool_calls[0]
            if not call.id or call.id in seen_calls or call.name not in validators:
                raise ModelError("Unknown tool or invalid/repeated tool call ID")
            arguments = _json_object(call.arguments)
            if not validators[call.name].is_valid(arguments):
                raise ModelError("Tool arguments do not match its schema")
            if turn == max_turns - 1:
                raise TurnLimitExceeded("No model turn remains to process a tool result")
            seen_calls.add(call.id)
            summary = arguments.pop("summary", None)
            result = await execute_tool(call.name, arguments)
            if not isinstance(result, str):
                raise TypeError("Tool handlers must return serialized text")
            content = "\n".join(part for part in (reply.content, summary) if part is not None) or None
            assistant_message = {"role": "assistant", "content": content, "tool_calls": [{
                "id": call.id, "type": "function", "function": {
                    "name": call.name, "arguments": json.dumps(arguments),
                },
            }]}
            tool_message = {"role": "tool", "tool_call_id": call.id, "content": result}
            history = base_history + [assistant_message, tool_message.copy()]
            compact_result = json.loads(result)
            compact_result.pop("snapshot", None)
            compact_result.get("observation", {}).pop("snapshot", None)
            tool_message["content"] = json.dumps(compact_result)
            base_history.extend([assistant_message, tool_message])
        elif reply.finish_reason == "stop" and not reply.tool_calls:
            value = _json_object(reply.content)
            try:
                return output_type.model_validate(value, strict=True)
            except ValidationError:
                raise ModelError("Final response does not match the outcome contract") from None
        else:
            raise ModelError("Model response was incomplete or unsupported")
    raise TurnLimitExceeded("Agent exceeded its model turn limit")
