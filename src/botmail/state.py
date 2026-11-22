"""Local read/unread tracking."""

from __future__ import annotations

import json
from pathlib import Path


class ReadState:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._read: set[str] = set()
        self._load()

    def _load(self) -> None:
        if self._path.is_file():
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self._read = set(data.get("read", []))

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps({"read": sorted(self._read)}, indent=2) + "\n",
            encoding="utf-8",
        )

    def is_read(self, message_id: str) -> bool:
        return message_id in self._read

    def mark_read(self, message_id: str) -> None:
        if message_id not in self._read:
            self._read.add(message_id)
            self._save()

    def unread_only(self, message_id: str) -> bool:
        return not self.is_read(message_id)