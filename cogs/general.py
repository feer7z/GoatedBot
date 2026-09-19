from __future__ import annotations

import time

import discord
from discord import app_commands
from discord.ext import commands

from config import EMBEDS_DIR
from utils.layout_loader import load_layout_view


class General(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="ping", description="Check the bot's response time.")
    async def ping(self, interaction: discord.Interaction) -> None:
        started_at = time.perf_counter()
        await interaction.response.defer(thinking=True)
        response_latency = round((time.perf_counter() - started_at) * 1000)

        raw_gateway_latency = self.bot.latency
        gateway_latency = "n/a" if raw_gateway_latency != raw_gateway_latency else str(round(raw_gateway_latency * 1000))

        view = load_layout_view(
            EMBEDS_DIR / "ping.json",
            values={"gateway_latency": gateway_latency, "response_latency": str(response_latency)},
            timeout=None,
        )
        await interaction.followup.send(view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(General(bot))
