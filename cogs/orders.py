from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from config import CURRENCY_SYMBOL, EMBEDS_DIR
from utils import emojis
from utils.brawlstars_api import (
    BrawlStarsAPIError,
    BrawlStarsClient,
    count_power_eleven_brawlers,
    find_best_winstreak_brawler,
    find_brawler,
    normalize_tag,
)
from utils.layout_loader import CallbackMap, load_layout_view
from utils.modal_helpers import add_text_field
from utils.panel_utils import post_panel
from utils.permissions import staff_only
from utils.pricing import (
    calculate_other_price,
    calculate_prestige_price,
    calculate_rank_price,
    calculate_winstreak_price,
    current_prestige_from_trophies,
    get_current_ranked_tier,
    get_other_option,
    normalize_rank_input,
    parse_prestige_level,
    rank_distance,
    trophies_required_for_prestige,
)
from utils.ticket_actions import create_ticket_channel, finalize_ticket_order, register_fill_details_handler


async def _lookup_player(raw_tag: str) -> tuple[dict | None, str | None]:
    if not raw_tag.strip():
        return None, "No player tag was provided."
    client = BrawlStarsClient()
    try:
        player = await client.get_player(raw_tag)
        return player, None
    except BrawlStarsAPIError as error:
        return None, str(error)
    finally:
        await client.close()


async def _start_pending_ticket(
    interaction: discord.Interaction,
    order_type: str,
    slug: str,
    service_kind: str,
) -> None:
    await interaction.response.defer(ephemeral=True, thinking=True)

    guild = interaction.guild
    opener = interaction.user
    if guild is None or not isinstance(opener, discord.Member):
        await interaction.followup.send("This can only be used from inside the server.", ephemeral=True)
        return

    channel = await create_ticket_channel(
        guild, opener, order_type, slug, summary_lines=[], extra={"service_kind": service_kind}, pending=True,
    )
    await interaction.followup.send(f"Your ticket is ready: {channel.mention}", ephemeral=True)


class RankedOrderModal(discord.ui.Modal):
    def __init__(self, is_duo_carry: bool) -> None:
        title = "Rank Carry Order" if is_duo_carry else "Rank Boost Order"
        super().__init__(title=title)
        self.is_duo_carry = is_duo_carry
        self.player_tag = add_text_field(
            self, "Brawl Stars Player Tag", placeholder="#ABC123XYZ", required=True, max_length=15,
        )
        self.desired_rank = add_text_field(
            self, "Desired Rank", placeholder="e.g. Legendary I or Pro", required=True, max_length=30,
        )
        self.payment_method = add_text_field(
            self, "Payment Method", placeholder="e.g. PayPal F&F", required=True, max_length=50,
        )
        self.notes = add_text_field(
            self,
            "Notes (optional)",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=300,
        )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await handle_ranked_submission(interaction, self)


async def handle_ranked_submission(interaction: discord.Interaction, modal: RankedOrderModal) -> None:
    await interaction.response.defer(ephemeral=True, thinking=True)

    desired_rank = normalize_rank_input(modal.desired_rank.value)
    if desired_rank is None:
        await interaction.followup.send(
            "I couldn't recognize that rank. Please use a format like `Legendary I` or `Pro`, "
            "then click Fill Order Details again.",
            ephemeral=True,
        )
        return

    player, api_error = await _lookup_player(modal.player_tag.value)
    if player is None:
        await interaction.followup.send(
            f"I couldn't look up that account, so I can't calculate an exact price ({api_error}). "
            "Please double check the player tag and click Fill Order Details again.",
            ephemeral=True,
        )
        return

    starting_rank = get_current_ranked_tier(player)
    if starting_rank is None:
        await interaction.followup.send(
            f"**{player.get('name', 'That account')}** doesn't have Ranked data yet this season — they need "
            "to play at least one Ranked match first. Click Fill Order Details again once they have.",
            ephemeral=True,
        )
        return

    distance = rank_distance(starting_rank, desired_rank)
    if distance is None or distance <= 0:
        await interaction.followup.send(
            f"**{player.get('name', 'That account')}** is already at {starting_rank}, which is at or above "
            f"{desired_rank}. Pick a higher rank and click Fill Order Details again.",
            ephemeral=True,
        )
        return

    p11_count = count_power_eleven_brawlers(player)
    breakdown = calculate_rank_price(starting_rank, desired_rank, p11_count, modal.is_duo_carry)

    order_type = "Rank Carry (Duo)" if modal.is_duo_carry else "Rank Boost (Solo)"

    summary_lines = [
        emojis.field(emojis.PAPER, "Player Tag", normalize_tag(modal.player_tag.value)),
        emojis.field(emojis.INFO, "Account", f"{player.get('name', 'Unknown')} ({player.get('trophies', 0):,} trophies)"),
        emojis.field(emojis.rank_emoji(starting_rank), "Starting Rank", starting_rank),
        emojis.field(emojis.rank_emoji(desired_rank), "Desired Rank", desired_rank),
        emojis.field(emojis.QUESTION, "Type", order_type),
        emojis.field(emojis.P11, "Power 11 Brawlers", str(p11_count)),
        emojis.field(emojis.PAYMENT_METHOD, "Payment Method", modal.payment_method.value),
    ]
    if modal.notes.value:
        summary_lines.append(emojis.field(emojis.PAPER, "Notes", modal.notes.value))
    if breakdown is not None:
        summary_lines.append(emojis.field(emojis.GOATED, "Price", breakdown.formatted(CURRENCY_SYMBOL)))
        for note in breakdown.notes:
            summary_lines.append(f"-# {note}")

    extra = {
        "price": breakdown.final_price if breakdown is not None else None,
        "payment_method": modal.payment_method.value,
        "player_tag": normalize_tag(modal.player_tag.value),
    }

    await finalize_ticket_order(interaction, order_type, summary_lines, extra)


class WinstreakOrderModal(discord.ui.Modal):
    def __init__(self) -> None:
        super().__init__(title="Winstreak Boost Order")
        self.player_tag = add_text_field(
            self, "Brawl Stars Player Tag", placeholder="#ABC123XYZ", required=True, max_length=15,
        )
        self.payment_method = add_text_field(
            self, "Payment Method", placeholder="e.g. PayPal F&F", required=True, max_length=50,
        )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await handle_winstreak_submission(interaction, self)


async def handle_winstreak_submission(interaction: discord.Interaction, modal: WinstreakOrderModal) -> None:
    await interaction.response.defer(ephemeral=True, thinking=True)

    player, api_error = await _lookup_player(modal.player_tag.value)
    if player is None:
        await interaction.followup.send(
            f"I couldn't look up that account, so I can't calculate an exact price ({api_error}). "
            "Please double check the player tag and click Fill Order Details again.",
            ephemeral=True,
        )
        return

    brawler = find_best_winstreak_brawler(player)
    if brawler is None:
        await interaction.followup.send(
            f"**{player.get('name', 'That account')}** doesn't have any win streak data yet. "
            "They need to win at least one match in a row first.",
            ephemeral=True,
        )
        return

    current_streak = brawler.get("maxWinStreak", 0)
    target, breakdown = calculate_winstreak_price(current_streak)

    summary_lines = [
        emojis.field(emojis.PLAYER, "Player Tag", normalize_tag(modal.player_tag.value)),
        emojis.field(emojis.INFO, "Account", player.get("name", "Unknown")),
        emojis.field(emojis.PAPER, "Brawler", brawler.get("name", "Unknown")),
        emojis.field(emojis.WINSTREAK, "Current Best Streak", f"{current_streak} wins"),
        emojis.field(emojis.WINSTREAK, "Target Streak", f"{target} wins"),
        emojis.field(emojis.PAYMENT_METHOD, "Payment Method", modal.payment_method.value),
        emojis.field(emojis.GOATED, "Price", breakdown.formatted(CURRENCY_SYMBOL)),
    ]
    for note in breakdown.notes:
        summary_lines.append(f"-# {note}")

    extra = {
        "price": breakdown.final_price,
        "payment_method": modal.payment_method.value,
        "brawler_name": brawler.get("name", "Unknown"),
        "player_tag": normalize_tag(modal.player_tag.value),
    }

    await finalize_ticket_order(interaction, "Winstreak Boost", summary_lines, extra)


class PrestigeOrderModal(discord.ui.Modal):
    def __init__(self, is_duo_carry: bool) -> None:
        title = "Prestige Carry Order" if is_duo_carry else "Prestige Boost Order"
        super().__init__(title=title)
        self.is_duo_carry = is_duo_carry
        self.player_tag = add_text_field(
            self, "Brawl Stars Player Tag", placeholder="#ABC123XYZ", required=True, max_length=15,
        )
        self.brawler_name = add_text_field(
            self, "Brawler Name", placeholder="e.g. Spike", required=True, max_length=30,
        )
        self.desired_prestige = add_text_field(
            self, "Desired Prestige", placeholder="e.g. P3", required=True, max_length=10,
        )
        self.payment_method = add_text_field(
            self, "Payment Method", placeholder="e.g. PayPal F&F", required=True, max_length=50,
        )
        self.notes = add_text_field(
            self,
            "Notes (optional)",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=300,
        )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await handle_prestige_submission(interaction, self)


async def handle_prestige_submission(interaction: discord.Interaction, modal: PrestigeOrderModal) -> None:
    await interaction.response.defer(ephemeral=True, thinking=True)

    desired_level = parse_prestige_level(modal.desired_prestige.value)
    if desired_level is None:
        await interaction.followup.send(
            "I couldn't recognize that Prestige level. Please use a format like `P3`, then click "
            "Fill Order Details again.",
            ephemeral=True,
        )
        return

    player, api_error = await _lookup_player(modal.player_tag.value)
    if player is None:
        await interaction.followup.send(
            f"I couldn't look up that account, so I can't calculate an exact price ({api_error}). "
            "Please double check the player tag and click Fill Order Details again.",
            ephemeral=True,
        )
        return

    brawler = find_brawler(player, modal.brawler_name.value)
    if brawler is None:
        await interaction.followup.send(
            f"**{player.get('name', 'That account')}** doesn't seem to have a brawler named "
            f'"{modal.brawler_name.value}" unlocked. Double check the spelling and click Fill Order Details again.',
            ephemeral=True,
        )
        return

    current_trophies = brawler.get("trophies", 0)
    breakdown = calculate_prestige_price(current_trophies, desired_level, modal.is_duo_carry)

    if breakdown is None:
        current_prestige = current_prestige_from_trophies(current_trophies)
        await interaction.followup.send(
            f"**{brawler.get('name', modal.brawler_name.value)}** is already at Prestige {current_prestige} "
            f"({current_trophies:,} trophies) on that account, which is at or above P{desired_level}. "
            "Pick a higher Prestige level and click Fill Order Details again.",
            ephemeral=True,
        )
        return

    order_type = "Prestige Carry (Duo)" if modal.is_duo_carry else "Prestige Boost (Solo)"
    brawler_name = brawler.get("name", modal.brawler_name.value)

    summary_lines = [
        emojis.field(emojis.PAPER, "Player Tag", normalize_tag(modal.player_tag.value)),
        emojis.field(emojis.INFO, "Account", player.get("name", "Unknown")),
        emojis.field(emojis.PAPER, "Brawler", brawler_name),
        emojis.field(emojis.PAPER, "Current Trophies", f"{current_trophies:,}"),
        emojis.field(
            emojis.prestige_emoji(desired_level),
            "Desired Prestige",
            f"{emojis.with_prestige(desired_level)} ({trophies_required_for_prestige(desired_level):,} trophies)",
        ),
        emojis.field(emojis.QUESTION, "Type", order_type),
        emojis.field(emojis.PAYMENT_METHOD, "Payment Method", modal.payment_method.value),
    ]
    if modal.notes.value:
        summary_lines.append(emojis.field(emojis.PAPER, "Notes", modal.notes.value))
    summary_lines.append(emojis.field(emojis.GOATED, "Price", breakdown.formatted(CURRENCY_SYMBOL)))
    for note in breakdown.notes:
        summary_lines.append(f"-# {note}")

    extra = {
        "price": breakdown.final_price,
        "payment_method": modal.payment_method.value,
        "brawler_name": brawler_name,
        "starting_trophies": current_trophies,
        "player_tag": normalize_tag(modal.player_tag.value),
    }

    await finalize_ticket_order(interaction, order_type, summary_lines, extra)


class OtherOrderModal(discord.ui.Modal):
    def __init__(self, option_key: str) -> None:
        option = get_other_option(option_key)
        label = option["label"] if option else "Other Request"
        super().__init__(title=f"Order: {label}"[:45])
        self.option_key = option_key
        self.player_tag = add_text_field(
            self, "Brawl Stars Player Tag (optional)", placeholder="#ABC123XYZ", required=False, max_length=15,
        )
        detail_label = option["detail_label"] if option else "Describe exactly what you need"
        self.detail = add_text_field(
            self,
            detail_label[:45],
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=300,
        )
        self.payment_method = add_text_field(
            self, "Payment Method", placeholder="e.g. PayPal F&F", required=True, max_length=50,
        )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await handle_other_submission(interaction, self)


async def handle_other_submission(interaction: discord.Interaction, modal: OtherOrderModal) -> None:
    await interaction.response.defer(ephemeral=True, thinking=True)

    option = get_other_option(modal.option_key)
    order_type = option["label"] if option else "Other Request"

    breakdown = calculate_other_price(modal.option_key, modal.detail.value)

    summary_lines = [emojis.field(emojis.service_emoji(modal.option_key), "Service", order_type)]
    if modal.player_tag.value.strip():
        summary_lines.append(emojis.field(emojis.PAPER, "Player Tag", normalize_tag(modal.player_tag.value)))
    summary_lines.append(emojis.field(emojis.PAPER, "Details", modal.detail.value))
    summary_lines.append(emojis.field(emojis.PAYMENT_METHOD, "Payment Method", modal.payment_method.value))
    if breakdown is not None:
        if breakdown.final_price > 0:
            summary_lines.append(emojis.field(emojis.GOATED, "Price", breakdown.formatted(CURRENCY_SYMBOL)))
        for note in breakdown.notes:
            summary_lines.append(f"-# {note}")

    extra = {
        "price": breakdown.final_price if breakdown is not None and breakdown.final_price > 0 else None,
        "payment_method": modal.payment_method.value,
    }

    await finalize_ticket_order(interaction, order_type, summary_lines, extra)


def _build_modal_for_service_kind(service_kind: str) -> discord.ui.Modal | None:
    if service_kind == "ranked_carry":
        return RankedOrderModal(is_duo_carry=True)
    if service_kind == "ranked_boost":
        return RankedOrderModal(is_duo_carry=False)
    if service_kind == "prestige_solo":
        return PrestigeOrderModal(is_duo_carry=False)
    if service_kind == "prestige_duo":
        return PrestigeOrderModal(is_duo_carry=True)
    if service_kind == "other_winstreak_boost":
        return WinstreakOrderModal()
    if service_kind and service_kind.startswith("other_"):
        return OtherOrderModal(option_key=service_kind[len("other_") :])
    return None


async def _handle_fill_details(interaction: discord.Interaction, ticket: dict) -> None:
    modal = _build_modal_for_service_kind(ticket.get("service_kind", ""))
    if modal is None:
        await interaction.response.send_message(
            "Something went wrong determining this ticket's order type. Please contact staff.", ephemeral=True,
        )
        return
    await interaction.response.send_modal(modal)


async def _on_order_ranked_carry(interaction: discord.Interaction) -> None:
    await _start_pending_ticket(interaction, "Rank Carry (Duo)", "rank-carry", "ranked_carry")


async def _on_order_ranked_boost(interaction: discord.Interaction) -> None:
    await _start_pending_ticket(interaction, "Rank Boost (Solo)", "rank-boost", "ranked_boost")


async def _on_order_prestige_solo(interaction: discord.Interaction) -> None:
    await _start_pending_ticket(interaction, "Prestige Boost (Solo)", "prestige-boost", "prestige_solo")


async def _on_order_prestige_duo(interaction: discord.Interaction) -> None:
    await _start_pending_ticket(interaction, "Prestige Carry (Duo)", "prestige-carry", "prestige_duo")


async def _on_order_other_select(interaction: discord.Interaction) -> None:
    values = interaction.data.get("values", []) if interaction.data else []
    if not values:
        await interaction.response.send_message("Please choose a service from the menu.", ephemeral=True)
        return
    option_key = values[0]
    option = get_other_option(option_key)
    order_type = option["label"] if option else "Other Request"
    slug = option_key.replace("_", "-")
    await _start_pending_ticket(interaction, order_type, slug, f"other_{option_key}")


def ranked_panel_callbacks() -> CallbackMap:
    return {
        "order_ranked_carry": _on_order_ranked_carry,
        "order_ranked_boost": _on_order_ranked_boost,
    }


def prestige_panel_callbacks() -> CallbackMap:
    return {
        "order_prestige_solo": _on_order_prestige_solo,
        "order_prestige_duo": _on_order_prestige_duo,
    }


def other_panel_callbacks() -> CallbackMap:
    return {"order_other_select": _on_order_other_select}


class Orders(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="ranked", description="Post the ranked boosting order panel.")
    @staff_only()
    async def ranked(self, interaction: discord.Interaction) -> None:
        view = load_layout_view(EMBEDS_DIR / "ranked.json", callbacks=ranked_panel_callbacks(), timeout=None)
        await post_panel(interaction, view)

    @app_commands.command(name="prestiges", description="Post the prestige boosting order panel.")
    @staff_only()
    async def prestiges(self, interaction: discord.Interaction) -> None:
        view = load_layout_view(EMBEDS_DIR / "prestiges.json", callbacks=prestige_panel_callbacks(), timeout=None)
        await post_panel(interaction, view)

    @app_commands.command(name="other", description="Post the other services order panel.")
    @staff_only()
    async def other(self, interaction: discord.Interaction) -> None:
        view = load_layout_view(EMBEDS_DIR / "other.json", callbacks=other_panel_callbacks(), timeout=None)
        await post_panel(interaction, view)


async def setup(bot: commands.Bot) -> None:
    register_fill_details_handler(_handle_fill_details)
    await bot.add_cog(Orders(bot))
