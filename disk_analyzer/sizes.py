"""Запросы топа крупнейших файлов и папок в каталоге."""
from __future__ import annotations

import sqlite3


def top_files(conn: sqlite3.Connection, scan_id: int, limit: int = 20) -> list[tuple[str, int]]:
    rows = conn.execute(
        "SELECT path, size FROM entries WHERE scan_id = ? AND is_dir = 0 "
        "ORDER BY size DESC LIMIT ?",
        (scan_id, limit),
    ).fetchall()
    return list(rows)


def top_dirs(conn: sqlite3.Connection, scan_id: int, limit: int = 20) -> list[tuple[str, int]]:
    rows = conn.execute(
        "SELECT path, size FROM entries WHERE scan_id = ? AND is_dir = 1 "
        "ORDER BY size DESC LIMIT ?",
        (scan_id, limit),
    ).fetchall()
    return list(rows)


def top_extensions(
    conn: sqlite3.Connection, scan_id: int, limit: int = 20
) -> list[tuple[str, int, int]]:
    """Возвращает (расширение, суммарный размер, количество файлов)."""
    rows = conn.execute(
        "SELECT COALESCE(NULLIF(ext, ''), '(без расширения)') AS e, "
        "SUM(size) AS total, COUNT(*) AS cnt "
        "FROM entries WHERE scan_id = ? AND is_dir = 0 "
        "GROUP BY e ORDER BY total DESC LIMIT ?",
        (scan_id, limit),
    ).fetchall()
    return list(rows)


def children(conn: sqlite3.Connection, scan_id: int, parent: str) -> list[tuple[str, int, int]]:
    """Прямые потомки директории `parent`: (путь, размер, is_dir), по убыванию размера."""
    rows = conn.execute(
        "SELECT path, size, is_dir FROM entries WHERE scan_id = ? AND parent = ? AND path != ? "
        "ORDER BY size DESC",
        (scan_id, parent, parent),
    ).fetchall()
    return list(rows)
