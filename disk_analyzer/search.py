"""Поиск по сохранённому каталогу файлов."""
from __future__ import annotations

import sqlite3


def search(
    conn: sqlite3.Connection,
    scan_id: int,
    name: str | None = None,
    ext: str | None = None,
    min_size: int | None = None,
    max_size: int | None = None,
    after: str | None = None,
    before: str | None = None,
    dirs_only: bool = False,
    files_only: bool = False,
    limit: int = 100,
) -> list[tuple[str, int, int, str]]:
    """Возвращает список (путь, размер, is_dir, mtime), отсортированный по размеру."""
    clauses = ["scan_id = ?"]
    params: list = [scan_id]

    if name:
        clauses.append("name LIKE ? ESCAPE '\\'")
        params.append(f"%{_escape_like(name)}%")
    if ext:
        clauses.append("ext = ?")
        params.append(ext if ext.startswith(".") else f".{ext}")
    if min_size is not None:
        clauses.append("size >= ?")
        params.append(min_size)
    if max_size is not None:
        clauses.append("size <= ?")
        params.append(max_size)
    if after:
        clauses.append("mtime >= ?")
        params.append(after)
    if before:
        clauses.append("mtime <= ?")
        params.append(before)
    if dirs_only:
        clauses.append("is_dir = 1")
    if files_only:
        clauses.append("is_dir = 0")

    query = (
        "SELECT path, size, is_dir, mtime FROM entries WHERE "
        + " AND ".join(clauses)
        + " ORDER BY size DESC LIMIT ?"
    )
    params.append(limit)
    return list(conn.execute(query, params).fetchall())


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
