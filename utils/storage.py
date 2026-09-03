from __future__ import annotations

import asyncio
import json
from typing import Any

from config import DATA_DIR, TICKETS_FILE

_LOCK = asyncio.Lock()


def _ensure_store() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not TICKETS_FILE.exists():
        TICKETS_FILE.write_text("{}", encoding="utf-8")


def _read_all() -> dict[str, Any]:
    _ensure_store()
    raw_text = TICKETS_FILE.read_text(encoding="utf-8")
    if not raw_text.strip():
        return {}
    return json.loads(raw_text)


def _write_all(data: dict[str, Any]) -> None:
    _ensure_store()
    TICKETS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


async def get_all_tickets() -> dict[str, Any]:
    async with _LOCK:
        return _read_all()


async def get_ticket(channel_id: int) -> dict[str, Any] | None:
    async with _LOCK:
        return _read_all().get(str(channel_id))


async def create_ticket(channel_id: int, record: dict[str, Any]) -> dict[str, Any]:
    async with _LOCK:
        tickets = _read_all()
        tickets[str(channel_id)] = record
        _write_all(tickets)
        return record


async def update_ticket(channel_id: int, **fields: Any) -> dict[str, Any] | None:
    async with _LOCK:
        tickets = _read_all()
        key = str(channel_id)
        if key not in tickets:
            return None
        tickets[key].update(fields)
        _write_all(tickets)
        return tickets[key]


async def delete_ticket(channel_id: int) -> None:
    async with _LOCK:
        tickets = _read_all()
        tickets.pop(str(channel_id), None)
        _write_all(tickets)
