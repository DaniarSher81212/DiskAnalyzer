"""Диалоговый агент: LLM + инструменты поверх каталога дисков."""
from __future__ import annotations

import sqlite3

from . import tools as tools_module
from .providers import Provider

SYSTEM_PROMPT = (
    "Ты — ассистент внутри программы disk-analyzer, которая анализирует содержимое "
    "дисков компьютера пользователя. У тебя есть инструменты для чтения каталога файлов "
    "(сканы, топы папок/файлов, поиск дубликатов, поиск по имени) и инструмент "
    "propose_deletion для предложения удаления файлов и папок. "
    "Удаление происходит через корзину ОС — файлы можно восстановить. "
    "Перед вызовом propose_deletion всегда сначала найди конкретные пути через другие "
    "инструменты и покажи пользователю что именно и почему предлагаешь удалить. "
    "Если свежего скана нет — предложи вызвать scan_disk. "
    "Отвечай кратко и по-русски, если пользователь пишет по-русски."
)

MAX_TOOL_ITERATIONS = 12


class Agent:
    def __init__(self, provider: Provider, conn: sqlite3.Connection, system: str = SYSTEM_PROMPT):
        self.provider = provider
        self.conn = conn
        self.system = system
        self.history: list[dict] = []

    def ask(self, user_message: str) -> str:
        self.history.append({"role": "user", "content": user_message})

        for _ in range(MAX_TOOL_ITERATIONS):
            turn = self.provider.chat(self.history, tools_module.TOOLS, self.system)

            if not turn.tool_calls:
                self.history.append({"role": "assistant", "content": turn.content})
                return turn.content or ""

            self.history.append({
                "role": "assistant",
                "content": turn.content,
                "tool_calls": turn.tool_calls,
            })
            for call in turn.tool_calls:
                result = tools_module.dispatch(self.conn, call.name, call.input)
                self.history.append({
                    "role": "tool_result",
                    "tool_call_id": call.id,
                    "name": call.name,
                    "content": result,
                })

        return "Слишком много шагов подряд — остановился, чтобы не зациклиться. Уточните запрос."
