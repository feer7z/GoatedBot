from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from config import EMBEDS_DIR
from utils.layout_loader import load_layout_view
from utils.permissions import staff_only
from utils.support_actions import support_panel_callbacks


class Support(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="support", description="Post the support ticket panel.")
    @staff_only()
    async def support(self, interaction: discord.Interaction) -> None:
        view = load_layout_view(EMBEDS_DIR / "support.json", callbacks=support_panel_callbacks(), timeout=None)
        await interaction.response.send_message(view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Support(bot))
