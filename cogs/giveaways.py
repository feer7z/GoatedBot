from __future__ import annotations

import time

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config import EMBEDS_NO_COMMANDS_DIR
from utils.giveaways import add_entry, create_giveaway, get_active_giveaways, get_giveaway, parse_duration, pick_winners, update_giveaway
from utils.layout_loader import CallbackMap, load_layout_view
from utils.permissions import staff_only


def _entry_count_text(entries: list[int]) -> str:
    return str(len(entries))


def _render_giveaway_view(giveaway: dict) -> discord.ui.LayoutView:
    end_display = f"<t:{int(giveaway['end_timestamp'])}:R>"
    return load_layout_view(
        EMBEDS_NO_COMMANDS_DIR / "giveaway.json",
        values={
            "prize": giveaway["prize"],
            "winner_count": str(giveaway["winner_count"]),
            "end_timestamp_display": end_display,
            "host_mention": f"<@{giveaway['host_id']}>",
            "entry_count": _entry_count_text(giveaway["entries"]),
        },
        callbacks=giveaway_entry_callbacks(),
        timeout=None,
    )


async def _handle_giveaway_enter(interaction: discord.Interaction) -> None:
    message = interaction.message
    if message is None:
        return

    giveaway = await get_giveaway(message.id)
    if giveaway is None or giveaway.get("ended"):
        await interaction.response.send_message("This giveaway has ended.", ephemeral=True)
        return

    added = await add_entry(message.id, interaction.user.id)
    if not added:
        await interaction.response.send_message("You're already entered into this giveaway!", ephemeral=True)
        return

    updated = await get_giveaway(message.id)
    await interaction.response.edit_message(view=_render_giveaway_view(updated))


def giveaway_entry_callbacks() -> CallbackMap:
    return {"giveaway_enter": _handle_giveaway_enter}


async def _end_giveaway(bot: commands.Bot, giveaway: dict) -> None:
    channel = bot.get_channel(giveaway["channel_id"])
    if not isinstance(channel, discord.TextChannel):
        await update_giveaway(giveaway["message_id"], ended=True)
        return

    winners = pick_winners(giveaway["entries"], channel.guild, giveaway["winner_count"])
    await update_giveaway(giveaway["message_id"], ended=True, winners=winners)

    winners_display = ", ".join(f"<@{uid}>" for uid in winners) if winners else "No valid entries"

    try:
        message = await channel.fetch_message(giveaway["message_id"])
        ended_view = load_layout_view(
            EMBEDS_NO_COMMANDS_DIR / "giveaway_ended.json",
            values={
                "prize": giveaway["prize"],
                "winners_display": winners_display,
                "entry_count": _entry_count_text(giveaway["entries"]),
            },
            timeout=None,
        )
        await message.edit(view=ended_view)
    except discord.NotFound:
        pass

    if winners:
        await channel.send(
            f"🎉 Congratulations {winners_display}! You won **{giveaway['prize']}**.",
            allowed_mentions=discord.AllowedMentions(users=True),
        )
    else:
        await channel.send(f"The giveaway for **{giveaway['prize']}** ended with no valid entries.")


class Giveaways(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.check_giveaways.start()

    def cog_unload(self) -> None:
        self.check_giveaways.cancel()

    @tasks.loop(seconds=30)
    async def check_giveaways(self) -> None:
        now = time.time()
        for giveaway in await get_active_giveaways():
            if now >= giveaway["end_timestamp"]:
                await _end_giveaway(self.bot, giveaway)

    @check_giveaways.before_loop
    async def before_check_giveaways(self) -> None:
        await self.bot.wait_until_ready()

    @app_commands.command(name="giveaway", description="Start a giveaway.")
    @app_commands.describe(
        prize="What are you giving away?",
        duration="e.g. 1h, 30m, 2d, 1d12h",
        winners="Number of winners",
    )
    @staff_only()
    async def giveaway(
        self,
        interaction: discord.Interaction,
        prize: str,
        duration: str,
        winners: app_commands.Range[int, 1, 20] = 1,
    ) -> None:
        seconds = parse_duration(duration)
        if seconds is None:
            await interaction.response.send_message(
                "I couldn't parse that duration. Try something like `1h`, `30m`, or `2d12h`.", ephemeral=True,
            )
            return

        record = {
            "message_id": None,
            "channel_id": interaction.channel_id,
            "prize": prize,
            "winner_count": winners,
            "end_timestamp": time.time() + seconds,
            "host_id": interaction.user.id,
            "entries": [],
            "ended": False,
        }

        await interaction.response.send_message(view=_render_giveaway_view(record))
        message = await interaction.original_response()

        record["message_id"] = message.id
        await create_giveaway(message.id, record)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Giveaways(bot))
