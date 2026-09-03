from __future__ import annotations

import discord
from discord.ext import commands

from utils.ticket_actions import process_completion_screenshot


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


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Tickets(bot))
