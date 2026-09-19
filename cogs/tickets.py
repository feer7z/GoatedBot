from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from utils.ticket_actions import (
    process_completion_screenshot,
    run_call_booster,
    run_close_ticket,
    run_mark_completed,
    run_mark_paid,
)


class Tickets(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        if not message.attachments:
            return
        await process_completion_screenshot(message)

    @app_commands.command(name="close", description="Close the ticket in this channel.")
    async def close(self, interaction: discord.Interaction) -> None:
        await run_close_ticket(interaction)

    @app_commands.command(name="paid", description="Mark this ticket as paid and notify the boosters.")
    async def paid(self, interaction: discord.Interaction) -> None:
        await run_mark_paid(interaction)

    @app_commands.command(name="completed", description="Mark this ticket as completed and request a screenshot.")
    async def completed(self, interaction: discord.Interaction) -> None:
        await run_mark_completed(interaction)

    @app_commands.command(name="callbooster", description="Ping the booster role in this ticket.")
    async def callbooster(self, interaction: discord.Interaction) -> None:
        await run_call_booster(interaction)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Tickets(bot))
