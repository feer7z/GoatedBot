from __future__ import annotations

import discord
from discord import ui

from config import ACCENT_COLOR, CURRENCY_SYMBOL, EMBEDS_NO_COMMANDS_DIR, SERVER_ID
from utils import emojis
from utils.brawlstars_api import (
    BrawlStarsAPIError,
    BrawlStarsClient,
    count_power_eleven_brawlers,
    find_best_winstreak_brawler,
    find_closest_brawler_below_threshold,
    normalize_tag,
)
from utils.layout_loader import CallbackMap, load_layout_view
from utils.modal_helpers import add_text_field
from utils.pricing import (
    calculate_prestige_price,
    calculate_rank_price,
    calculate_winstreak_price,
    get_current_ranked_tier,
    next_rank_tier,
    trophies_required_for_prestige,
)
from utils.ticket_actions import create_ticket_channel


async def send_tag_request_dm(user: discord.abc.User) -> bool:
    view = load_layout_view(
        EMBEDS_NO_COMMANDS_DIR / "welcome_tag_request.json",
        callbacks=welcome_panel_callbacks(),
        timeout=None,
    )
    try:
        await user.send(view=view)
        return True
    except discord.Forbidden:
        return False
    except discord.HTTPException:
        return False


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


async def handle_cta_get_offer(interaction: discord.Interaction) -> None:
    await interaction.response.send_modal(WelcomeTagModal())


def welcome_panel_callbacks() -> CallbackMap:
    return {"welcome_show_offers": _handle_show_offers}


def cta_callbacks() -> CallbackMap:
    return {"cta_get_offer": handle_cta_get_offer}


async def _resolve_guild_and_member(
    interaction: discord.Interaction,
) -> tuple[discord.Guild | None, discord.Member | None]:
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
    pending: bool = False,
) -> None:
    if not interaction.response.is_done():
        await interaction.response.defer(thinking=True)

    guild, opener = await _resolve_guild_and_member(interaction)
    if guild is None or opener is None:
        await interaction.followup.send(
            "I couldn't confirm your membership in the server right now. Please try again shortly."
        )
        return

    channel = await create_ticket_channel(guild, opener, order_type, slug, summary_lines, extra, pending=pending)
    await interaction.followup.send(f"Done! Your ticket is ready: {channel.mention}")


async def _handle_tag_submission(interaction: discord.Interaction, raw_tag: str) -> None:
    await interaction.response.defer(thinking=True, ephemeral=interaction.guild is not None)

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
        ui.TextDisplay(
            f"# {emojis.GOATED} Offers for {player.get('name', 'you')}\n"
            "Pick whichever sounds good — one click opens a ticket."
        )
    )
    container.add_item(ui.Separator(visible=True))

    winstreak_brawler = find_best_winstreak_brawler(player)
    if winstreak_brawler is not None:
        current_streak = winstreak_brawler.get("maxWinStreak", 0)
        target_streak, winstreak_price = calculate_winstreak_price(current_streak)

        winstreak_section = ui.Section(
            ui.TextDisplay(
                f"**{emojis.WINSTREAK} Winstreak Boost**\n{winstreak_brawler.get('name', 'Your brawler')}'s best "
                f"streak is {current_streak} wins. Beat it and reach {target_streak} for "
                f"{winstreak_price.formatted(CURRENCY_SYMBOL)}."
            ),
            accessory=ui.Button(
                style=discord.ButtonStyle.success, label="Order This", custom_id="welcome_order_winstreak",
            ),
        )

        async def on_order_winstreak(interaction: discord.Interaction) -> None:
            await _create_offer_ticket(
                interaction,
                order_type="Winstreak Boost",
                slug="winstreak-boost",
                summary_lines=[
                    emojis.field(emojis.PAPER, "Player Tag", tag),
                    emojis.field(emojis.INFO, "Account", player.get("name", "Unknown")),
                    emojis.field(emojis.PAPER, "Brawler", winstreak_brawler.get("name", "Unknown")),
                    emojis.field(emojis.WINSTREAK, "Current Best Streak", f"{current_streak} wins"),
                    emojis.field(emojis.WINSTREAK, "Target Streak", f"{target_streak} wins"),
                    emojis.field(emojis.GOATED, "Price", winstreak_price.formatted(CURRENCY_SYMBOL)),
                    emojis.field(emojis.PAYMENT_METHOD, "Payment Method", "To be confirmed"),
                ],
                extra={
                    "price": winstreak_price.final_price,
                    "payment_method": None,
                    "brawler_name": winstreak_brawler.get("name", "Unknown"),
                    "player_tag": tag,
                    "service_kind": "other_winstreak_boost",
                },
            )

        winstreak_section.accessory.callback = on_order_winstreak
        container.add_item(winstreak_section)
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
                    f"**{emojis.PRESTIGE_3} Prestige Push**\n{brawler_name} is at {brawler_trophies:,} trophies — "
                    f"your closest brawler to {emojis.with_prestige(3)} ({prestige_threshold:,}). Get there for "
                    f"{prestige_price.formatted(CURRENCY_SYMBOL)}."
                ),
                accessory=ui.Button(
                    style=discord.ButtonStyle.success, label="Order This", custom_id="welcome_order_prestige",
                ),
            )

            async def on_order_prestige(interaction: discord.Interaction) -> None:
                await _create_offer_ticket(
                    interaction,
                    order_type="Prestige Boost (Solo)",
                    slug="prestige-boost",
                    summary_lines=[
                        emojis.field(emojis.PAPER, "Player Tag", tag),
                        emojis.field(emojis.INFO, "Account", player.get("name", "Unknown")),
                        emojis.field(emojis.PAPER, "Brawler", brawler_name),
                        emojis.field(emojis.PAPER, "Current Trophies", f"{brawler_trophies:,}"),
                        emojis.field(
                            emojis.PRESTIGE_3,
                            "Desired Prestige",
                            f"{emojis.with_prestige(3)} ({prestige_threshold:,} trophies)",
                        ),
                        emojis.field(emojis.GOATED, "Price", prestige_price.formatted(CURRENCY_SYMBOL)),
                        emojis.field(emojis.PAYMENT_METHOD, "Payment Method", "To be confirmed"),
                    ],
                    extra={
                        "price": prestige_price.final_price,
                        "payment_method": None,
                        "brawler_name": brawler_name,
                        "starting_trophies": brawler_trophies,
                        "player_tag": tag,
                        "service_kind": "prestige_solo",
                    },
                )

            prestige_section.accessory.callback = on_order_prestige
            container.add_item(prestige_section)
            container.add_item(ui.Separator(visible=True))

    starting_rank = get_current_ranked_tier(player)
    desired_rank = next_rank_tier(starting_rank) if starting_rank else None

    if starting_rank is not None and desired_rank is not None:
        p11_count = count_power_eleven_brawlers(player)
        rank_price = calculate_rank_price(starting_rank, desired_rank, p11_count, is_duo_carry=False)

        if rank_price is not None:
            ranked_section = ui.Section(
                ui.TextDisplay(
                    f"**{emojis.rank_emoji(desired_rank)} Ranked Push**\nYou're at {emojis.with_rank(starting_rank)} "
                    f"right now. Climb to {emojis.with_rank(desired_rank)} for {rank_price.formatted(CURRENCY_SYMBOL)}."
                ),
                accessory=ui.Button(
                    style=discord.ButtonStyle.success, label="Order This", custom_id="welcome_order_ranked",
                ),
            )

            async def on_order_ranked(interaction: discord.Interaction) -> None:
                await _create_offer_ticket(
                    interaction,
                    order_type="Rank Boost (Solo)",
                    slug="rank-boost",
                    summary_lines=[
                        emojis.field(emojis.PAPER, "Player Tag", tag),
                        emojis.field(emojis.INFO, "Account", player.get("name", "Unknown")),
                        emojis.field(emojis.rank_emoji(starting_rank), "Starting Rank", starting_rank),
                        emojis.field(emojis.rank_emoji(desired_rank), "Desired Rank", desired_rank),
                        emojis.field(emojis.P11, "Power 11 Brawlers", str(p11_count)),
                        emojis.field(emojis.GOATED, "Price", rank_price.formatted(CURRENCY_SYMBOL)),
                        emojis.field(emojis.PAYMENT_METHOD, "Payment Method", "To be confirmed"),
                    ],
                    extra={
                        "price": rank_price.final_price,
                        "payment_method": None,
                        "player_tag": tag,
                        "service_kind": "ranked_boost",
                    },
                )

            ranked_section.accessory.callback = on_order_ranked
            container.add_item(ranked_section)
            container.add_item(ui.Separator(visible=True))
    else:
        ranked_section = ui.Section(
            ui.TextDisplay(
                f"**{emojis.PRO} Ranked Push**\nWant to climb the Ranked ladder too? Play at least one Ranked "
                "match first so we can read your current tier — or open a ticket now and tell us yourself."
            ),
            accessory=ui.Button(
                style=discord.ButtonStyle.secondary, label="Ask About Ranked", custom_id="welcome_order_ranked",
            ),
        )

        async def on_order_ranked(interaction: discord.Interaction) -> None:
            await _create_offer_ticket(
                interaction,
                order_type="Rank Boost (Solo)",
                slug="rank-boost",
                summary_lines=[],
                extra={"player_tag": tag, "service_kind": "ranked_boost"},
                pending=True,
            )

        ranked_section.accessory.callback = on_order_ranked
        container.add_item(ranked_section)

    view.add_item(container)
    return view
