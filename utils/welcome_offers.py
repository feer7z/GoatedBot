from __future__ import annotations

import discord
from discord import ui

from config import ACCENT_COLOR, CURRENCY_SYMBOL, EMBEDS_NO_COMMANDS_DIR, SERVER_ID
from utils.brawlstars_api import (
    BrawlStarsAPIError,
    BrawlStarsClient,
    find_closest_brawler_below_threshold,
    normalize_tag,
)
from utils.layout_loader import CallbackMap, load_layout_view
from utils.modal_helpers import add_text_field
from utils.pricing import calculate_prestige_price, calculate_victory_milestone_price, trophies_required_for_prestige
from utils.ticket_actions import create_ticket_channel


async def send_tag_request_dm(user: discord.abc.User) -> None:
    view = load_layout_view(
        EMBEDS_NO_COMMANDS_DIR / "welcome_tag_request.json",
        callbacks=welcome_panel_callbacks(),
        timeout=None,
    )
    try:
        await user.send(view=view)
    except discord.Forbidden:
        pass


class WelcomeTagModal(ui.Modal):
    def __init__(self) -> None:
        super().__init__(title="Show Me Offers")
        self.player_tag = add_text_field(
            self, "Brawl Stars Player Tag", placeholder="#ABC123XYZ", required=True, max_length=15,
        )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await _handle_tag_submission(interaction, self.player_tag.value)


async def _handle_show_offers(interaction: discord.Interaction) -> None:
    await interaction.response.send_modal(WelcomeTagModal())


def welcome_panel_callbacks() -> CallbackMap:
    return {"welcome_show_offers": _handle_show_offers}


async def _resolve_guild_and_member(interaction: discord.Interaction) -> tuple[discord.Guild | None, discord.Member | None]:
    guild = interaction.client.get_guild(SERVER_ID)
    if guild is None:
        return None, None
    member = guild.get_member(interaction.user.id)
    if member is None:
        try:
            member = await guild.fetch_member(interaction.user.id)
        except discord.NotFound:
            member = None
    return guild, member


async def _create_offer_ticket(
    interaction: discord.Interaction,
    order_type: str,
    slug: str,
    summary_lines: list[str],
    extra: dict,
) -> None:
    await interaction.response.defer(thinking=True)

    guild, opener = await _resolve_guild_and_member(interaction)
    if guild is None or opener is None:
        await interaction.followup.send(
            "I couldn't confirm your membership in the server right now. Please try again shortly."
        )
        return

    channel = await create_ticket_channel(guild, opener, order_type, slug, summary_lines, extra)
    await interaction.followup.send(f"Done! Your ticket is ready: {channel.mention}")


async def _handle_tag_submission(interaction: discord.Interaction, raw_tag: str) -> None:
    await interaction.response.defer(thinking=True)

    client = BrawlStarsClient()
    try:
        player = await client.get_player(raw_tag)
    except BrawlStarsAPIError as error:
        await interaction.followup.send(
            f"I couldn't look up that account ({error}). Please double check the tag and try again."
        )
        return
    finally:
        await client.close()

    tag = normalize_tag(raw_tag)
    view = _build_offers_view(player, tag)
    await interaction.followup.send(view=view)


def _build_offers_view(player: dict, tag: str) -> ui.LayoutView:
    view = ui.LayoutView(timeout=None)
    container = ui.Container(accent_color=ACCENT_COLOR)
    container.add_item(
        ui.TextDisplay(f"# Offers for {player.get('name', 'you')}\nPick whichever sounds good — one click opens a ticket.")
    )
    container.add_item(ui.Separator(visible=True))

    victories = player.get("3vs3Victories", 0)
    target_victories, victory_price = calculate_victory_milestone_price(victories)

    victory_section = ui.Section(
        ui.TextDisplay(
            f"**🏆 Victory Milestone**\nYou're at {victories:,} 3v3 Victories. Reach {target_victories:,} "
            f"for {victory_price.formatted(CURRENCY_SYMBOL)}."
        ),
        accessory=ui.Button(style=discord.ButtonStyle.success, label="Order This", custom_id="welcome_order_victories"),
    )

    async def on_order_victories(interaction: discord.Interaction) -> None:
        await _create_offer_ticket(
            interaction,
            order_type="Victory Milestone Boost",
            slug="victory-milestone",
            summary_lines=[
                f"**Player Tag** — {tag}",
                f"**Current 3v3 Victories** — {victories:,}",
                f"**Target** — {target_victories:,}",
                f"**Price** — {victory_price.formatted(CURRENCY_SYMBOL)}",
            ],
            extra={"price": victory_price.final_price, "payment_method": None, "player_tag": tag},
        )

    victory_section.accessory.callback = on_order_victories
    container.add_item(victory_section)
    container.add_item(ui.Separator(visible=True))

    prestige_threshold = trophies_required_for_prestige(3)
    prestige_brawler = find_closest_brawler_below_threshold(player, prestige_threshold)

    if prestige_brawler is not None:
        brawler_name = prestige_brawler.get("name", "Unknown")
        brawler_trophies = prestige_brawler.get("trophies", 0)
        prestige_price = calculate_prestige_price(brawler_trophies, 3, is_duo_carry=False)

        if prestige_price is not None:
            prestige_section = ui.Section(
                ui.TextDisplay(
                    f"**⭐ Prestige Push**\n{brawler_name} is at {brawler_trophies:,} trophies — your closest "
                    f"brawler to Prestige 3 ({prestige_threshold:,}). Get there for "
                    f"{prestige_price.formatted(CURRENCY_SYMBOL)}."
                ),
                accessory=ui.Button(style=discord.ButtonStyle.success, label="Order This", custom_id="welcome_order_prestige"),
            )

            async def on_order_prestige(interaction: discord.Interaction) -> None:
                await _create_offer_ticket(
                    interaction,
                    order_type="Prestige Boost (Solo)",
                    slug="prestige-boost",
                    summary_lines=[
                        f"**Player Tag** — {tag}",
                        f"**Brawler** — {brawler_name}",
                        f"**Current Trophies** — {brawler_trophies:,}",
                        f"**Desired Prestige** — P3 ({prestige_threshold:,} trophies)",
                        f"**Price** — {prestige_price.formatted(CURRENCY_SYMBOL)}",
                    ],
                    extra={
                        "price": prestige_price.final_price,
                        "payment_method": None,
                        "brawler_name": brawler_name,
                        "starting_trophies": brawler_trophies,
                        "player_tag": tag,
                    },
                )

            prestige_section.accessory.callback = on_order_prestige
            container.add_item(prestige_section)
            container.add_item(ui.Separator(visible=True))

    ranked_section = ui.Section(
        ui.TextDisplay(
            "**🎯 Ranked Push**\nWant to climb the Ranked ladder too? We can't read your Ranked tier "
            "automatically — open a ticket and tell us your current rank, and we'll quote you on the spot."
        ),
        accessory=ui.Button(style=discord.ButtonStyle.secondary, label="Ask About Ranked", custom_id="welcome_order_ranked"),
    )

    async def on_order_ranked(interaction: discord.Interaction) -> None:
        await _create_offer_ticket(
            interaction,
            order_type="Ranked Push (Custom Quote)",
            slug="ranked-custom",
            summary_lines=[
                f"**Player Tag** — {tag}",
                "**Starting Rank** — Ask the client",
                "**Desired Rank** — Ask the client",
                "**Price** — To be confirmed by staff",
            ],
            extra={"price": None, "payment_method": None, "player_tag": tag},
        )

    ranked_section.accessory.callback = on_order_ranked
    container.add_item(ranked_section)

    view.add_item(container)
    return view
