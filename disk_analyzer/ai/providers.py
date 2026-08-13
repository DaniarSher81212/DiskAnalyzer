"""Провайдеро-независимый слой поверх LLM API.

Внутреннее представление истории диалога — список словарей одной из форм:
  {"role": "user", "content": "..."}
  {"role": "assistant", "content": "..." | None, "tool_calls": [ToolCall, ...]}
  {"role": "tool_result", "tool_call_id": "...", "name": "...", "content": "...", "is_error": bool}

Каждый провайдер сам переводит эту историю в свой формат при каждом вызове —
API у всех провайдеров без сохранения состояния, поэтому шлём историю целиком.
"""
from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from ..config import get_api_key, get_model, get_ollama_url


@dataclass
class ToolSpec:
    name: str
    description: str
    schema: dict  # JSON schema объекта входных параметров


@dataclass
class ToolCall:
    id: str
    name: str
    input: dict


@dataclass
class AssistantTurn:
    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)


class Provider(ABC):
    name: str

    @abstractmethod
    def chat(self, history: list[dict], tools: list[ToolSpec], system: str) -> AssistantTurn:
        """Отправляет историю диалога и инструменты, возвращает следующий ход ассистента."""


def _group_tool_results(history: list[dict]) -> list[dict]:
    """Схлопывает подряд идущие tool_result-записи, если это нужно провайдеру."""
    return history


class AnthropicProvider(Provider):
    name = "anthropic"

    def __init__(self, model: str | None = None, api_key: str | None = None, max_tokens: int = 4096):
        import anthropic

        resolved_key = api_key or os.environ.get("ANTHROPIC_API_KEY") or get_api_key("anthropic")
        self.client = anthropic.Anthropic(api_key=resolved_key) if resolved_key else anthropic.Anthropic()
        self.model = model or os.environ.get("DISK_ANALYZER_ANTHROPIC_MODEL") or get_model("anthropic") or "claude-opus-4-7"
        self.max_tokens = max_tokens

    def _to_messages(self, history: list[dict]) -> list[dict]:
        messages: list[dict] = []
        pending_tool_results: list[dict] = []

        def flush_tool_results():
            if pending_tool_results:
                messages.append({"role": "user", "content": list(pending_tool_results)})
                pending_tool_results.clear()

        for entry in history:
            role = entry["role"]
            if role == "user":
                flush_tool_results()
                messages.append({"role": "user", "content": entry["content"]})
            elif role == "assistant":
                flush_tool_results()
                blocks = []
                if entry.get("content"):
                    blocks.append({"type": "text", "text": entry["content"]})
                for tc in entry.get("tool_calls", []):
                    blocks.append({"type": "tool_use", "id": tc.id, "name": tc.name, "input": tc.input})
                messages.append({"role": "assistant", "content": blocks})
            elif role == "tool_result":
                pending_tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": entry["tool_call_id"],
                    "content": entry["content"],
                    "is_error": entry.get("is_error", False),
                })
        flush_tool_results()
        return messages

    def chat(self, history: list[dict], tools: list[ToolSpec], system: str) -> AssistantTurn:
        anthropic_tools = [
            {"name": t.name, "description": t.description, "input_schema": t.schema}
            for t in tools
        ]
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=self._to_messages(history),
            tools=anthropic_tools,
        )
        text_parts = []
        tool_calls = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(id=block.id, name=block.name, input=block.input))
        return AssistantTurn(content="".join(text_parts) or None, tool_calls=tool_calls)


class _OpenAICompatibleProvider(Provider):
    """Общая реализация для Chat Completions API (OpenAI и Ollama)."""

    def __init__(self, model: str, base_url: str | None = None, api_key: str | None = None, max_tokens: int = 4096):
        import openai

        kwargs = {}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = openai.OpenAI(api_key=api_key or "not-needed", **kwargs)
        self.model = model
        self.max_tokens = max_tokens

    def _to_messages(self, history: list[dict], system: str) -> list[dict]:
        messages: list[dict] = [{"role": "system", "content": system}]
        for entry in history:
            role = entry["role"]
            if role == "user":
                messages.append({"role": "user", "content": entry["content"]})
            elif role == "assistant":
                msg = {"role": "assistant", "content": entry.get("content")}
                tool_calls = entry.get("tool_calls", [])
                if tool_calls:
                    msg["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.name, "arguments": json.dumps(tc.input)},
                        }
                        for tc in tool_calls
                    ]
                messages.append(msg)
            elif role == "tool_result":
                messages.append({
                    "role": "tool",
                    "tool_call_id": entry["tool_call_id"],
                    "content": entry["content"],
                })
        return messages

    def chat(self, history: list[dict], tools: list[ToolSpec], system: str) -> AssistantTurn:
        oa_tools = [
            {
                "type": "function",
                "function": {"name": t.name, "description": t.description, "parameters": t.schema},
            }
            for t in tools
        ]
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=self._to_messages(history, system),
            tools=oa_tools,
        )
        message = response.choices[0].message
        tool_calls = [
            ToolCall(id=tc.id, name=tc.function.name, input=json.loads(tc.function.arguments or "{}"))
            for tc in (message.tool_calls or [])
        ]
        return AssistantTurn(content=message.content, tool_calls=tool_calls)


class OpenAIProvider(_OpenAICompatibleProvider):
    name = "openai"

    def __init__(self, model: str | None = None, api_key: str | None = None, max_tokens: int = 4096):
        super().__init__(
            model=model or os.environ.get("DISK_ANALYZER_OPENAI_MODEL") or get_model("openai") or "gpt-4o",
            api_key=api_key or os.environ.get("OPENAI_API_KEY") or get_api_key("openai"),
            max_tokens=max_tokens,
        )


class OllamaProvider(_OpenAICompatibleProvider):
    name = "ollama"

    def __init__(self, model: str | None = None, base_url: str | None = None, max_tokens: int = 4096):
        super().__init__(
            model=model or os.environ.get("DISK_ANALYZER_OLLAMA_MODEL") or get_model("ollama") or "llama3.1",
            base_url=(base_url or os.environ.get("DISK_ANALYZER_OLLAMA_URL") or get_ollama_url()) + "/v1",
            api_key="ollama",
            max_tokens=max_tokens,
        )


def get_provider(name: str) -> Provider:
    name = name.lower()
    if name == "anthropic":
        return AnthropicProvider()
    if name == "openai":
        return OpenAIProvider()
    if name == "ollama":
        return OllamaProvider()
    raise ValueError(f"Неизвестный провайдер: {name!r}. Доступны: anthropic, openai, ollama")
