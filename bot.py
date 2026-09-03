from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from config import BOT_TOKEN, EMBEDS_DIR, EMBEDS_NO_COMMANDS_DIR, SERVER_ID
from cogs.orders import other_panel_callbacks, prestige_panel_callbacks, ranked_panel_callbacks
from utils.layout_loader import load_layout_view
from utils.ticket_actions import paid_callbacks, review_prompt_callbacks, ticket_welcome_callbacks

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("goatedbot")

INITIAL_EXTENSIONS = (
    "cogs.general",
    "cogs.verification",
    "cogs.orders",
    "cogs.tickets",
)

intents = discord.Intents.default()
intents.members = True
intents.message_content = True


class GoatedBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(command_prefix=commands.when_mentioned, intents=intents)

    async def setup_hook(self) -> None:
        for extension in INITIAL_EXTENSIONS:
            await self.load_extension(extension)

        self._register_persistent_views()

        if SERVER_ID:
            guild = discord.Object(id=SERVER_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()

    def _register_persistent_views(self) -> None:
        self.add_view(load_layout_view(EMBEDS_DIR / "ranked.json", callbacks=ranked_panel_callbacks(), timeout=None))
        self.add_view(load_layout_view(EMBEDS_DIR / "prestiges.json", callbacks=prestige_panel_callbacks(), timeout=None))
        self.add_view(load_layout_view(EMBEDS_DIR / "other.json", callbacks=other_panel_callbacks(), timeout=None))

        self.add_view(
            load_layout_view(
                EMBEDS_NO_COMMANDS_DIR / "ticket_welcome.json",
                values={"opener_mention": "", "booster_mention": "", "summary_block": ""},
                callbacks=ticket_welcome_callbacks(),
                timeout=None,
            )
        )
        self.add_view(
            load_layout_view(
                EMBEDS_NO_COMMANDS_DIR / "paid.json",
                values={"booster_mention": ""},
                callbacks=paid_callbacks(),
                timeout=None,
            )
        )
        self.add_view(
            load_layout_view(
                EMBEDS_NO_COMMANDS_DIR / "review_prompt.json",
                values={"opener_mention": ""},
                callbacks=review_prompt_callbacks(),
                timeout=None,
            )
        )


bot = GoatedBot()


@bot.event
async def on_ready() -> None:
    user = bot.user
    logger.info("Logged in as %s (ID: %s)", user, user.id if user else "unknown")


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    if isinstance(error, app_commands.CheckFailure):
        message = "You don't have permission to use this command."
    else:
        logger.exception("Unhandled application command error", exc_info=error)
        message = "Something went wrong while running that command."

    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)


def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set. Add it to your .env file or Railway environment variables.")
    bot.run(BOT_TOKEN)


if __name__ == "__main__":
    main()
