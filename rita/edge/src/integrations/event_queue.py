from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable


class LocalEventQueue:
    """Simple FIFO queue persisted as JSON Lines on disk."""

    def __init__(self, queue_path: Path) -> None:
        self._queue_path = queue_path

    @property
    def path(self) -> Path:
        return self._queue_path

    def enqueue(self, event: dict[str, Any]) -> bool:
        try:
            self._queue_path.parent.mkdir(parents=True, exist_ok=True)
            with self._queue_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, ensure_ascii=False) + "\n")
            return True
        except Exception as exc:
            print(f"[WARN] No se pudo guardar evento en cola local: {exc}")
            return False

    def read_pending(self) -> list[dict[str, Any]]:
        if not self._queue_path.exists():
            return []

        pending: list[dict[str, Any]] = []
        try:
            with self._queue_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    text = line.strip()
                    if not text:
                        continue
                    try:
                        data = json.loads(text)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(data, dict):
                        pending.append(data)
        except Exception as exc:
            print(f"[WARN] No se pudo leer cola local: {exc}")
            return []
        return pending

    def retry_pending(self, send_func: Callable[[dict[str, Any]], bool]) -> tuple[int, int]:
        pending = self.read_pending()
        if not pending:
            return (0, 0)

        remaining: list[dict[str, Any]] = []
        sent = 0

        for event in pending:
            ok = False
            try:
                ok = bool(send_func(event))
            except Exception as exc:
                print(f"[WARN] Error al reenviar evento en cola: {exc}")
                ok = False
            if ok:
                sent += 1
            else:
                remaining.append(event)

        if not self._rewrite(remaining):
            return (sent, len(pending))

        return (sent, len(remaining))

    def _rewrite(self, events: list[dict[str, Any]]) -> bool:
        temp_path = self._queue_path.with_suffix(self._queue_path.suffix + ".tmp")
        try:
            self._queue_path.parent.mkdir(parents=True, exist_ok=True)
            with temp_path.open("w", encoding="utf-8") as handle:
                for event in events:
                    handle.write(json.dumps(event, ensure_ascii=False) + "\n")
            temp_path.replace(self._queue_path)
            return True
        except Exception as exc:
            print(f"[WARN] No se pudo actualizar cola local: {exc}")
            return False
