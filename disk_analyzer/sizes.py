"""Запросы топа крупнейших файлов и папок в каталоге."""
from __future__ import annotations

import sqlite3


def _under(under: str | None) -> tuple[str, list]:
    """Возвращает SQL-фрагмент и параметры для фильтра по поддереву."""
    if not under:
        return "", []
    prefix = under.rstrip("/").rstrip("\\")
    escaped = prefix.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return "AND (path = ? OR path LIKE ? ESCAPE '\\')", [prefix, escaped + "/%"]


def top_files(conn: sqlite3.Connection, scan_id: int, limit: int = 20, under: str | None = None) -> list[tuple[str, int]]:
    extra, params = _under(under)
    rows = conn.execute(
        f"SELECT path, size FROM entries WHERE scan_id = ? AND is_dir = 0 {extra} ORDER BY size DESC LIMIT ?",
        [scan_id, *params, limit],
    ).fetchall()
    return list(rows)


def top_dirs(conn: sqlite3.Connection, scan_id: int, limit: int = 20, under: str | None = None) -> list[tuple[str, int]]:
    extra, params = _under(under)
    rows = conn.execute(
        f"SELECT path, size FROM entries WHERE scan_id = ? AND is_dir = 1 {extra} ORDER BY size DESC LIMIT ?",
        [scan_id, *params, limit],
    ).fetchall()
    return list(rows)


def top_extensions(
    conn: sqlite3.Connection, scan_id: int, limit: int = 20, under: str | None = None
) -> list[tuple[str, int, int]]:
    """Возвращает (расширение, суммарный размер, количество файлов)."""
    extra, params = _under(under)
    rows = conn.execute(
        f"SELECT COALESCE(NULLIF(ext, ''), '(без расширения)') AS e, "
        f"SUM(size) AS total, COUNT(*) AS cnt "
        f"FROM entries WHERE scan_id = ? AND is_dir = 0 {extra} "
        f"GROUP BY e ORDER BY total DESC LIMIT ?",
        [scan_id, *params, limit],
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
