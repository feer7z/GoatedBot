from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from utils.welcome_offers import send_tag_request_dm


class Welcome(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        if member.bot:
            return
        await send_tag_request_dm(member)

    @app_commands.command(name="offers", description="See personalized starter offers by DM.")
    async def offers(self, interaction: discord.Interaction) -> None:
        await send_tag_request_dm(interaction.user)
        await interaction.response.send_message("Check your DMs! 📬", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Welcome(bot))
