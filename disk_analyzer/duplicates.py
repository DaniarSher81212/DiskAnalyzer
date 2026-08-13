"""Поиск файлов-дубликатов в каталоге по содержимому."""
from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass, field

PARTIAL_READ_BYTES = 65536
CHUNK_SIZE = 1 << 20  # 1 MiB


def _hash_file(path: str, limit: int | None = None) -> str | None:
    h = hashlib.blake2b(digest_size=16)
    try:
        with open(path, "rb") as f:
            if limit is not None:
                h.update(f.read(limit))
            else:
                while chunk := f.read(CHUNK_SIZE):
                    h.update(chunk)
    except OSError:
        return None
    return h.hexdigest()


@dataclass
class DuplicateGroup:
    size: int
    paths: list[str] = field(default_factory=list)

    @property
    def wasted_bytes(self) -> int:
        return self.size * (len(self.paths) - 1)


def find_duplicates(
    conn: sqlite3.Connection, scan_id: int, min_size: int = 1
) -> list[DuplicateGroup]:
    """Находит группы дублирующихся файлов внутри указанного скана.

    Трёхшаговая фильтрация: сначала группируем по размеру (дёшево),
    затем по хэшу первых 64КБ, затем по полному хэшу — так избегаем
    хэширования всего содержимого для заведомо уникальных файлов.
    """
    size_rows = conn.execute(
        "SELECT size, path FROM entries "
        "WHERE scan_id = ? AND is_dir = 0 AND size >= ? "
        "ORDER BY size",
        (scan_id, min_size),
    ).fetchall()

    by_size: dict[int, list[str]] = {}
    for size, path in size_rows:
        by_size.setdefault(size, []).append(path)
    size_candidates = {s: p for s, p in by_size.items() if len(p) > 1}

    partial_groups: dict[tuple[int, str], list[str]] = {}
    for size, paths in size_candidates.items():
        for path in paths:
            digest = _hash_file(path, PARTIAL_READ_BYTES)
            if digest is None:
                continue
            partial_groups.setdefault((size, digest), []).append(path)

    results: list[DuplicateGroup] = []
    for (size, _digest), paths in partial_groups.items():
        if len(paths) < 2:
            continue
        full_groups: dict[str, list[str]] = {}
        for path in paths:
            digest = _hash_file(path)
            if digest is None:
                continue
            full_groups.setdefault(digest, []).append(path)
        for group_paths in full_groups.values():
            if len(group_paths) > 1:
                results.append(DuplicateGroup(size=size, paths=sorted(group_paths)))

    results.sort(key=lambda g: g.wasted_bytes, reverse=True)
    return results
