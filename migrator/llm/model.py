import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Protocol

from openai import AsyncOpenAI, APIError

from .config import ModelConfig


class ModelError(RuntimeError):
    """A provider failure or unusable response, without request content."""


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: str


@dataclass(frozen=True)
class ModelResponse:
    content: str | None
    tool_calls: list[ToolCall]
    finish_reason: str


class ModelBackend(Protocol):
    async def generate(self, messages: list[dict], tools: list[dict], schema: dict) -> ModelResponse: ...


@dataclass
class ChatCompletionsBackend:
    client: AsyncOpenAI
    config: ModelConfig

    async def generate(self, messages: list[dict], tools: list[dict], schema: dict) -> ModelResponse:
        options = {"store": False} if self.config.provider == "openai" else {}
        if self.config.model == "gpt-6-luna":
            options["reasoning_effort"] = "none"
        if tools:
            options.update(tools=tools, tool_choice="auto", parallel_tool_calls=False)
        try:
            async with asyncio.timeout(self.config.timeout_seconds):
                response = await self.client.chat.completions.create(
                    model=self.config.model, messages=messages,
                    response_format={"type": "json_schema", "json_schema": {
                        "name": "agent_outcome", "strict": True, "schema": schema,
                    }}, **options,
                )
        except TimeoutError:
            raise ModelError("Model request timed out") from None
        except APIError as exc:
            raise ModelError(f"Model request failed: {exc}") from None
        if len(response.choices) != 1:
            raise ModelError("Expected one model response")
        choice = response.choices[0]
        message = choice.message
        if message.role != "assistant" or message.refusal:
            raise ModelError("Model did not provide an assistant answer")
        calls = []
        for call in message.tool_calls or []:
            if call.type != "function":
                raise ModelError("Only function calls are supported")
            calls.append(ToolCall(call.id, call.function.name, call.function.arguments))
        return ModelResponse(message.content, calls, choice.finish_reason)


@asynccontextmanager
async def connect_model(config: ModelConfig) -> AsyncIterator[ModelBackend]:
    async with AsyncOpenAI(
        api_key=config.api_key or "local-no-key",
        base_url=config.base_url or "https://api.openai.com/v1",
        timeout=config.timeout_seconds, max_retries=0,
    ) as client:
        yield ChatCompletionsBackend(client, config)
