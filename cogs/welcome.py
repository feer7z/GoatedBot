from __future__ import annotations

import asyncio

import discord
from discord import app_commands
from discord.ext import commands

from utils.permissions import staff_only
from utils.ticket_actions import register_cta_handler
from utils.welcome_offers import handle_cta_get_offer, send_tag_request_dm

BROADCAST_DELAY_SECONDS = 1.0


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
        delivered = await send_tag_request_dm(interaction.user)
        message = (
            "Check your DMs!"
            if delivered
            else "I couldn't DM you — please enable direct messages from server members and try again."
        )
        await interaction.response.send_message(message, ephemeral=True)

    @app_commands.command(name="offer", description="Send the personalized offers DM to a member.")
    @app_commands.describe(member="Who to send the offers DM to")
    @staff_only()
    async def offer(self, interaction: discord.Interaction, member: discord.Member) -> None:
        if member.bot:
            await interaction.response.send_message("Bots can't receive offers.", ephemeral=True)
            return

        delivered = await send_tag_request_dm(member)
        message = (
            f"Offers DM sent to {member.mention}."
            if delivered
            else f"Couldn't DM {member.mention} — they have direct messages disabled."
        )
        await interaction.response.send_message(
            message, ephemeral=True, allowed_mentions=discord.AllowedMentions.none(),
        )

    @app_commands.command(name="offerall", description="Send the personalized offers DM to every member.")
    @staff_only()
    async def offerall(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("This can only be used inside the server.", ephemeral=True)
            return

        await interaction.response.send_message(
            "Sending offers to every member. This runs slowly to respect Discord's rate limits — "
            "I'll report back when it's done.",
            ephemeral=True,
        )

        targets = [member for member in guild.members if not member.bot]
        delivered = 0
        blocked = 0

        for member in targets:
            if await send_tag_request_dm(member):
                delivered += 1
            else:
                blocked += 1
            await asyncio.sleep(BROADCAST_DELAY_SECONDS)

        await interaction.followup.send(
            f"Done — offers delivered to {delivered} member(s). {blocked} had DMs closed.", ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    register_cta_handler(handle_cta_get_offer)
    await bot.add_cog(Welcome(bot))
