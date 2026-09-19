from __future__ import annotations

import discord
from discord import ui


async def post_panel(interaction: discord.Interaction, view: ui.LayoutView, notice: str = "Panel posted.") -> None:
    await interaction.response.send_message(notice, ephemeral=True)
    channel = interaction.channel
    if channel is not None:
        await channel.send(view=view)
