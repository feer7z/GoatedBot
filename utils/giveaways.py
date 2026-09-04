from __future__ import annotations

import asyncio
import json
import random
import re

import discord

from config import DATA_DIR, GIVEAWAY_DEFAULT_WEIGHT, GIVEAWAY_ROLE_WEIGHTS, GIVEAWAYS_FILE

_LOCK = asyncio.Lock()

_DURATION_PATTERN = re.compile(r"(\d+)\s*(d|h|m|s)", re.IGNORECASE)
_UNIT_SECONDS = {"d": 86400, "h": 3600, "m": 60, "s": 1}


def parse_duration(raw_value: str) -> int | None:
    matches = _DURATION_PATTERN.findall(raw_value.strip())
    if not matches:
        return None
    total_seconds = sum(int(amount) * _UNIT_SECONDS[unit.lower()] for amount, unit in matches)
    return total_seconds if total_seconds > 0 else None


def _ensure_store() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not GIVEAWAYS_FILE.exists():
        GIVEAWAYS_FILE.write_text("{}", encoding="utf-8")


def _read_all() -> dict:
    _ensure_store()
    raw_text = GIVEAWAYS_FILE.read_text(encoding="utf-8")
    if not raw_text.strip():
        return {}
    return json.loads(raw_text)


def _write_all(data: dict) -> None:
    _ensure_store()
    GIVEAWAYS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


async def create_giveaway(message_id: int, record: dict) -> None:
    async with _LOCK:
        data = _read_all()
        data[str(message_id)] = record
        _write_all(data)


async def get_giveaway(message_id: int) -> dict | None:
    async with _LOCK:
        return _read_all().get(str(message_id))


async def update_giveaway(message_id: int, **fields) -> dict | None:
    async with _LOCK:
        data = _read_all()
        key = str(message_id)
        if key not in data:
            return None
        data[key].update(fields)
        _write_all(data)
        return data[key]


async def add_entry(message_id: int, user_id: int) -> bool:
    async with _LOCK:
        data = _read_all()
        key = str(message_id)
        record = data.get(key)
        if record is None or record.get("ended"):
            return False
        if user_id in record["entries"]:
            return False
        record["entries"].append(user_id)
        _write_all(data)
        return True


async def get_active_giveaways() -> list[dict]:
    async with _LOCK:
        data = _read_all()
        return [record for record in data.values() if not record.get("ended")]


def _weight_for_member(member: discord.Member | None) -> float:
    if member is None:
        return GIVEAWAY_DEFAULT_WEIGHT
    applicable = [
        weight
        for role_id, weight in GIVEAWAY_ROLE_WEIGHTS.items()
        if any(role.id == role_id for role in member.roles)
    ]
    return max(applicable) if applicable else GIVEAWAY_DEFAULT_WEIGHT


def pick_winners(entries: list[int], guild: discord.Guild | None, winner_count: int) -> list[int]:
    pool = [(user_id, _weight_for_member(guild.get_member(user_id) if guild else None)) for user_id in entries]
    winners: list[int] = []
    for _ in range(min(winner_count, len(pool))):
        total_weight = sum(weight for _, weight in pool)
        if total_weight <= 0:
            break
        roll = random.uniform(0, total_weight)
        cumulative = 0.0
        for index, (user_id, weight) in enumerate(pool):
            cumulative += weight
            if roll <= cumulative:
                winners.append(user_id)
                pool.pop(index)
                break
    return winners
