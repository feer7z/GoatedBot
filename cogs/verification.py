from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from config import EMBEDS_DIR
from utils.layout_loader import load_layout_view
from utils.permissions import staff_only


class Verification(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="verification", description="Post the account verification panel.")
    @staff_only()
    async def verification(self, interaction: discord.Interaction) -> None:
        view = load_layout_view(EMBEDS_DIR / "verification.json", timeout=None)
        await interaction.response.send_message(view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Verification(bot))
