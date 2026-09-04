from __future__ import annotations

from urllib.parse import quote

import aiohttp

from config import BRAWL_API_BASE_URL, BRAWL_API_KEY

POWER_ELEVEN_THRESHOLD = 11


class BrawlStarsAPIError(Exception):
    pass


def normalize_tag(raw_tag: str) -> str:
    cleaned = raw_tag.strip().upper().replace("O", "0")
    if not cleaned.startswith("#"):
        cleaned = f"#{cleaned}"
    return cleaned


def encode_tag(raw_tag: str) -> str:
    return quote(normalize_tag(raw_tag))


class BrawlStarsClient:
    def __init__(self) -> None:
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            headers = {"Authorization": f"Bearer {BRAWL_API_KEY}"}
            self._session = aiohttp.ClientSession(headers=headers)
        return self._session

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()

    async def get_player(self, raw_tag: str) -> dict:
        session = await self._get_session()
        url = f"{BRAWL_API_BASE_URL}/players/{encode_tag(raw_tag)}"
        async with session.get(url) as response:
            if response.status == 200:
                return await response.json()
            if response.status == 404:
                raise BrawlStarsAPIError("Player not found. Double check the player tag.")
            if response.status == 403:
                raise BrawlStarsAPIError(
                    "The Brawl Stars API rejected this request (403). The API key is likely not "
                    "allow-listed for the IP address making the request. If BRAWL_API_BASE_URL points "
                    "at bsproxy.royaleapi.dev, whitelist 45.79.218.79 on the key instead of this server's IP."
                )
            if response.status == 429:
                raise BrawlStarsAPIError("The Brawl Stars API rate limit was reached. Try again shortly.")
            raise BrawlStarsAPIError(f"The Brawl Stars API returned an unexpected status ({response.status}).")

    async def get_brawler(self, brawler_id_or_name: str) -> dict:
        session = await self._get_session()
        url = f"{BRAWL_API_BASE_URL}/brawlers/{quote(str(brawler_id_or_name))}"
        async with session.get(url) as response:
            if response.status == 200:
                return await response.json()
            if response.status == 404:
                raise BrawlStarsAPIError("Brawler not found.")
            raise BrawlStarsAPIError(f"The Brawl Stars API returned an unexpected status ({response.status}).")


def count_power_eleven_brawlers(player: dict) -> int:
    brawlers = player.get("brawlers", [])
    return sum(1 for brawler in brawlers if brawler.get("power", 0) >= POWER_ELEVEN_THRESHOLD)


def find_brawler(player: dict, brawler_name: str) -> dict | None:
    target = brawler_name.strip().lower()
    for brawler in player.get("brawlers", []):
        if brawler.get("name", "").strip().lower() == target:
            return brawler
    return None


def summarize_player(player: dict) -> str:
    name = player.get("name", "Unknown")
    trophies = player.get("trophies", 0)
    p11_count = count_power_eleven_brawlers(player)
    return f"{name} — {trophies:,} trophies, {p11_count} Power 11 brawlers"
