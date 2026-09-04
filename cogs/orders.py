from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from config import CURRENCY_SYMBOL, EMBEDS_DIR
from utils.brawlstars_api import (
    BrawlStarsAPIError,
    BrawlStarsClient,
    count_power_eleven_brawlers,
    find_brawler,
    normalize_tag,
)
from utils.layout_loader import CallbackMap, load_layout_view
from utils.modal_helpers import add_text_field
from utils.permissions import staff_only
from utils.pricing import (
    calculate_other_price,
    calculate_prestige_price,
    calculate_rank_price,
    current_prestige_from_trophies,
    get_other_option,
    normalize_rank_input,
    parse_prestige_level,
    rank_distance,
    trophies_required_for_prestige,
)
from utils.ticket_actions import send_order_confirmation


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


class RankedOrderModal(discord.ui.Modal):
    def __init__(self, is_duo_carry: bool) -> None:
        title = "Rank Carry Order" if is_duo_carry else "Rank Boost Order"
        super().__init__(title=title)
        self.is_duo_carry = is_duo_carry
        self.player_tag = add_text_field(
            self, "Brawl Stars Player Tag", placeholder="#ABC123XYZ", required=True, max_length=15,
        )
        self.starting_rank = add_text_field(
            self, "Starting Rank", placeholder="e.g. Diamond II", required=True, max_length=30,
        )
        self.desired_rank = add_text_field(
            self, "Desired Rank", placeholder="e.g. Legendary I", required=True, max_length=30,
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

    starting_rank = normalize_rank_input(modal.starting_rank.value)
    desired_rank = normalize_rank_input(modal.desired_rank.value)

    if starting_rank is None or desired_rank is None:
        await interaction.followup.send(
            "I couldn't recognize one of the ranks you entered. Please use a format like "
            "`Diamond II` or `Legendary I` and try again.",
            ephemeral=True,
        )
        return

    distance = rank_distance(starting_rank, desired_rank)
    if distance is None or distance <= 0:
        await interaction.followup.send("Your desired rank needs to be higher than your starting rank.", ephemeral=True)
        return

    player, api_error = await _lookup_player(modal.player_tag.value)
    p11_count = count_power_eleven_brawlers(player) if player else None
    breakdown = calculate_rank_price(starting_rank, desired_rank, p11_count, modal.is_duo_carry)

    order_type = "Rank Carry (Duo)" if modal.is_duo_carry else "Rank Boost (Solo)"
    slug = "rank-carry" if modal.is_duo_carry else "rank-boost"

    summary_lines = [
        f"**Player Tag** — {normalize_tag(modal.player_tag.value)}",
        f"**Starting Rank** — {starting_rank}",
        f"**Desired Rank** — {desired_rank}",
        f"**Type** — {order_type}",
    ]
    if player is not None:
        summary_lines.append(f"**Account** — {player.get('name', 'Unknown')} ({player.get('trophies', 0):,} trophies)")
        summary_lines.append(f"**Power 11 Brawlers** — {p11_count}")
    else:
        summary_lines.append(f"**Account Lookup** — Unavailable ({api_error})")
    summary_lines.append(f"**Payment Method** — {modal.payment_method.value}")
    if modal.notes.value:
        summary_lines.append(f"**Notes** — {modal.notes.value}")
    if breakdown is not None:
        summary_lines.append(f"**Price** — {breakdown.formatted(CURRENCY_SYMBOL)}")
        for note in breakdown.notes:
            summary_lines.append(f"-# {note}")

    extra = {
        "price": breakdown.final_price if breakdown is not None else None,
        "payment_method": modal.payment_method.value,
    }

    await send_order_confirmation(interaction, order_type, slug, summary_lines, extra)


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
            "I couldn't recognize that Prestige level. Please use a format like `P3` and try again.",
            ephemeral=True,
        )
        return

    player, api_error = await _lookup_player(modal.player_tag.value)
    if player is None:
        await interaction.followup.send(
            f"I couldn't look up that account, so I can't calculate an exact price ({api_error}). "
            "Please double check the player tag and try again.",
            ephemeral=True,
        )
        return

    brawler = find_brawler(player, modal.brawler_name.value)
    if brawler is None:
        await interaction.followup.send(
            f"**{player.get('name', 'That account')}** doesn't seem to have a brawler named "
            f'"{modal.brawler_name.value}" unlocked. Double check the spelling and try again.',
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
            "Pick a higher Prestige level.",
            ephemeral=True,
        )
        return

    order_type = "Prestige Carry (Duo)" if modal.is_duo_carry else "Prestige Boost (Solo)"
    slug = "prestige-carry" if modal.is_duo_carry else "prestige-boost"
    brawler_name = brawler.get("name", modal.brawler_name.value)

    summary_lines = [
        f"**Player Tag** — {normalize_tag(modal.player_tag.value)}",
        f"**Account** — {player.get('name', 'Unknown')}",
        f"**Brawler** — {brawler_name}",
        f"**Current Trophies** — {current_trophies:,}",
        f"**Desired Prestige** — P{desired_level} ({trophies_required_for_prestige(desired_level):,} trophies)",
        f"**Type** — {order_type}",
        f"**Payment Method** — {modal.payment_method.value}",
    ]
    if modal.notes.value:
        summary_lines.append(f"**Notes** — {modal.notes.value}")
    summary_lines.append(f"**Price** — {breakdown.formatted(CURRENCY_SYMBOL)}")
    for note in breakdown.notes:
        summary_lines.append(f"-# {note}")

    extra = {
        "price": breakdown.final_price,
        "payment_method": modal.payment_method.value,
        "brawler_name": brawler_name,
        "starting_trophies": current_trophies,
        "player_tag": normalize_tag(modal.player_tag.value),
    }

    await send_order_confirmation(interaction, order_type, slug, summary_lines, extra)


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
    slug = modal.option_key.replace("_", "-")

    breakdown = calculate_other_price(modal.option_key, modal.detail.value)

    summary_lines = [f"**Service** — {order_type}"]
    if modal.player_tag.value.strip():
        summary_lines.append(f"**Player Tag** — {normalize_tag(modal.player_tag.value)}")
    summary_lines.append(f"**Details** — {modal.detail.value}")
    summary_lines.append(f"**Payment Method** — {modal.payment_method.value}")
    if breakdown is not None:
        if breakdown.final_price > 0:
            summary_lines.append(f"**Price** — {breakdown.formatted(CURRENCY_SYMBOL)}")
        for note in breakdown.notes:
            summary_lines.append(f"-# {note}")

    extra = {
        "price": breakdown.final_price if breakdown is not None and breakdown.final_price > 0 else None,
        "payment_method": modal.payment_method.value,
    }

    await send_order_confirmation(interaction, order_type, slug, summary_lines, extra)


async def _on_order_ranked_carry(interaction: discord.Interaction) -> None:
    await interaction.response.send_modal(RankedOrderModal(is_duo_carry=True))


async def _on_order_ranked_boost(interaction: discord.Interaction) -> None:
    await interaction.response.send_modal(RankedOrderModal(is_duo_carry=False))


async def _on_order_prestige_solo(interaction: discord.Interaction) -> None:
    await interaction.response.send_modal(PrestigeOrderModal(is_duo_carry=False))


async def _on_order_prestige_duo(interaction: discord.Interaction) -> None:
    await interaction.response.send_modal(PrestigeOrderModal(is_duo_carry=True))


async def _on_order_other_select(interaction: discord.Interaction) -> None:
    values = interaction.data.get("values", []) if interaction.data else []
    if not values:
        await interaction.response.send_message("Please choose a service from the menu.", ephemeral=True)
        return
    await interaction.response.send_modal(OtherOrderModal(option_key=values[0]))


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
        await interaction.response.send_message(view=view)

    @app_commands.command(name="prestiges", description="Post the prestige boosting order panel.")
    @staff_only()
    async def prestiges(self, interaction: discord.Interaction) -> None:
        view = load_layout_view(EMBEDS_DIR / "prestiges.json", callbacks=prestige_panel_callbacks(), timeout=None)
        await interaction.response.send_message(view=view)

    @app_commands.command(name="other", description="Post the other services order panel.")
    @staff_only()
    async def other(self, interaction: discord.Interaction) -> None:
        view = load_layout_view(EMBEDS_DIR / "other.json", callbacks=other_panel_callbacks(), timeout=None)
        await interaction.response.send_message(view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Orders(bot))
