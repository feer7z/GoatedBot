from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from config import EMBEDS_DIR
from utils.layout_loader import load_layout_view


class General(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="ping", description="Check whether the bot is online.")
    async def ping(self, interaction: discord.Interaction) -> None:
        view = load_layout_view(EMBEDS_DIR / "ping.json", timeout=None)
        await interaction.response.send_message(view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(General(bot))
