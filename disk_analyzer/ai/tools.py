"""Инструменты, которые AI-агент может вызывать поверх каталога дисков.

Только чтение — агент не может ничего удалять или изменять на диске.
Все инструменты работают через уже существующие модули disk_analyzer
(db/scanner/sizes/search/duplicates), чтобы не дублировать логику CLI.
"""
from __future__ import annotations

import sqlite3

from .. import db as db_module
from .. import duplicates as duplicates_module
from .. import scanner as scanner_module
from .. import search as search_module
from .. import sizes as sizes_module
from .providers import ToolSpec


def _human(n: float) -> str:
    for unit in ("Б", "КБ", "МБ", "ГБ", "ТБ", "ПБ"):
        if abs(n) < 1024:
            return f"{n:,.1f} {unit}".replace(",", " ")
        n /= 1024
    return f"{n:,.1f} ЭБ".replace(",", " ")


def _resolve_scan_id(conn: sqlite3.Connection, scan_id: int | None) -> int:
    if scan_id:
        return scan_id
    found = db_module.latest_scan_id(conn)
    if found is None:
        raise ValueError("Ещё нет ни одного завершённого скана. Сначала вызови scan_disk.")
    return found


TOOLS: list[ToolSpec] = [
    ToolSpec(
        name="list_scans",
        description="Показать историю сканирований дисков: какие пути сканировались, когда, сколько файлов и байт найдено.",
        schema={"type": "object", "properties": {}, "additionalProperties": False},
    ),
    ToolSpec(
        name="scan_disk",
        description=(
            "Просканировать путь (например, 'C:\\' или 'D:\\Data') и сохранить каталог файлов в БД. "
            "Полное сканирование диска может занять от секунд до пары минут. Вызывай, только когда "
            "нет свежего скана нужного пути (проверь через list_scans)."
        ),
        schema={
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Путь для сканирования"}},
            "required": ["path"],
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name="top_folders",
        description="Крупнейшие папки по суммарному размеру (по всей глубине) в последнем скане.",
        schema={
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Сколько папок вернуть", "default": 20},
                "scan_id": {"type": "integer", "description": "ID конкретного скана (по умолчанию — последний)"},
            },
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name="top_files",
        description="Крупнейшие отдельные файлы в последнем скане.",
        schema={
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 20},
                "scan_id": {"type": "integer"},
            },
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name="top_extensions",
        description="Расширения файлов, занимающие больше всего места (суммарно и по количеству файлов).",
        schema={
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 20},
                "scan_id": {"type": "integer"},
            },
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name="list_folder",
        description="Показать прямые дочерние файлы и папки указанного пути, отсортированные по размеру.",
        schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Путь к папке, например 'C:\\Users\\DAN\\Desktop'"},
                "scan_id": {"type": "integer"},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name="find_duplicates",
        description="Найти группы файлов-дубликатов по содержимому (не по имени). Может быть медленным на больших порогах.",
        schema={
            "type": "object",
            "properties": {
                "min_size_bytes": {"type": "integer", "description": "Игнорировать файлы меньше этого размера", "default": 1048576},
                "limit": {"type": "integer", "description": "Сколько групп вернуть", "default": 30},
                "scan_id": {"type": "integer"},
            },
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name="propose_deletion",
        description=(
            "Предложить пользователю переместить файлы или папки в корзину. "
            "Показывает список и суммарный размер, запрашивает подтверждение y/N. "
            "Вызывай только после того, как нашёл конкретные кандидаты через другие инструменты."
        ),
        schema={
            "type": "object",
            "properties": {
                "paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Список путей для удаления",
                },
                "reason": {
                    "type": "string",
                    "description": "Почему эти файлы можно удалить (показывается пользователю)",
                },
                "total_size_bytes": {
                    "type": "integer",
                    "description": "Суммарный размер в байтах",
                },
            },
            "required": ["paths", "reason"],
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name="search_files",
        description="Поиск файлов/папок в каталоге по имени, расширению, размеру, дате изменения.",
        schema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Подстрока в имени"},
                "ext": {"type": "string", "description": "Расширение, например .pdf"},
                "min_size_bytes": {"type": "integer"},
                "max_size_bytes": {"type": "integer"},
                "after": {"type": "string", "description": "ISO-дата, mtime >= after"},
                "before": {"type": "string", "description": "ISO-дата, mtime <= before"},
                "dirs_only": {"type": "boolean", "default": False},
                "files_only": {"type": "boolean", "default": False},
                "limit": {"type": "integer", "default": 50},
                "scan_id": {"type": "integer"},
            },
            "additionalProperties": False,
        },
    ),
]


def dispatch(conn: sqlite3.Connection, name: str, args: dict) -> str:
    try:
        if name == "list_scans":
            rows = conn.execute(
                "SELECT id, root, started_at, finished_at, file_count, dir_count, total_size, errors "
                "FROM scans ORDER BY id DESC LIMIT 20"
            ).fetchall()
            if not rows:
                return "Сканирований пока нет."
            lines = []
            for scan_id, root, started, finished, fc, dc, size, errors in rows:
                status = "завершено" if finished else "прервано"
                lines.append(
                    f"[{scan_id}] {root} — {status}, файлов={fc}, папок={dc}, "
                    f"объём={_human(size)}, ошибок={errors}, начато={started}"
                )
            return "\n".join(lines)

        if name == "scan_disk":
            path = args["path"]
            scan_id = scanner_module.scan(path, conn)
            row = conn.execute(
                "SELECT file_count, dir_count, total_size, errors FROM scans WHERE id = ?", (scan_id,)
            ).fetchone()
            file_count, dir_count, total_size, errors = row
            return (
                f"Скан завершён: scan_id={scan_id}, файлов={file_count}, папок={dir_count}, "
                f"объём={_human(total_size)}, ошибок={errors}"
            )

        if name == "top_folders":
            scan_id = _resolve_scan_id(conn, args.get("scan_id"))
            rows = sizes_module.top_dirs(conn, scan_id, args.get("limit", 20))
            return "\n".join(f"{_human(size):>12}  {path}" for path, size in rows) or "Пусто."

        if name == "top_files":
            scan_id = _resolve_scan_id(conn, args.get("scan_id"))
            rows = sizes_module.top_files(conn, scan_id, args.get("limit", 20))
            return "\n".join(f"{_human(size):>12}  {path}" for path, size in rows) or "Пусто."

        if name == "top_extensions":
            scan_id = _resolve_scan_id(conn, args.get("scan_id"))
            rows = sizes_module.top_extensions(conn, scan_id, args.get("limit", 20))
            return "\n".join(f"{_human(total):>12}  {ext:<15} ({cnt} файлов)" for ext, total, cnt in rows) or "Пусто."

        if name == "list_folder":
            scan_id = _resolve_scan_id(conn, args.get("scan_id"))
            rows = sizes_module.children(conn, scan_id, args["path"])
            if not rows:
                return "Папка пуста или не найдена в каталоге."
            return "\n".join(
                f"{'DIR ' if is_dir else 'FILE'} {_human(size):>12}  {path}" for path, size, is_dir in rows
            )

        if name == "find_duplicates":
            scan_id = _resolve_scan_id(conn, args.get("scan_id"))
            groups = duplicates_module.find_duplicates(conn, scan_id, min_size=args.get("min_size_bytes", 1048576))
            limit = args.get("limit", 30)
            if not groups:
                return "Дубликаты не найдены."
            lines = [f"Всего групп: {len(groups)}"]
            for g in groups[:limit]:
                lines.append(f"-- {_human(g.size)} x{len(g.paths)}, лишнее: {_human(g.wasted_bytes)}")
                for p in g.paths:
                    lines.append(f"   {p}")
            return "\n".join(lines)

        if name == "propose_deletion":
            paths = args.get("paths", [])
            reason = args.get("reason", "")
            total_size = args.get("total_size_bytes")
            if not paths:
                return "Список путей пуст — нечего удалять."
            print(f"\n{'─' * 60}")
            print(f"AI предлагает переместить в корзину ({reason}):")
            for p in paths:
                print(f"  {p}")
            if total_size:
                print(f"Итого: {_human(total_size)}")
            print('─' * 60)
            try:
                answer = input("Переместить в корзину? [y/N]: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("")
                return "Операция отменена пользователем."
            if answer != "y":
                return "Пользователь отказался от удаления."
            from send2trash import send2trash
            deleted, errors = [], []
            for path in paths:
                try:
                    send2trash(path)
                    deleted.append(path)
                except Exception as exc:
                    errors.append(f"{path}: {exc}")
            parts = [f"Перемещено в корзину: {len(deleted)} объект(ов)."]
            if total_size and deleted:
                parts.append(f"Освобождено: {_human(total_size * len(deleted) / len(paths))}.")
            if errors:
                parts.append(f"Ошибки: {'; '.join(errors)}")
            return " ".join(parts)

        if name == "search_files":
            scan_id = _resolve_scan_id(conn, args.get("scan_id"))
            rows = search_module.search(
                conn,
                scan_id,
                name=args.get("name"),
                ext=args.get("ext"),
                min_size=args.get("min_size_bytes"),
                max_size=args.get("max_size_bytes"),
                after=args.get("after"),
                before=args.get("before"),
                dirs_only=args.get("dirs_only", False),
                files_only=args.get("files_only", False),
                limit=args.get("limit", 50),
            )
            if not rows:
                return "Ничего не найдено."
            return "\n".join(
                f"{'DIR ' if is_dir else 'FILE'} {_human(size):>12}  {mtime or '':<25} {path}"
                for path, size, is_dir, mtime in rows
            )

        return f"Неизвестный инструмент: {name}"
    except Exception as exc:  # инструмент должен вернуть текст ошибки модели, а не уронить агента
        return f"Ошибка при выполнении {name}: {exc}"
