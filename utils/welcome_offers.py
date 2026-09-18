from future import annotations

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
from utils.pricing import (
calculate_prestige_price,
calculate_rank_price,
calculate_victory_milestone_price,
calculate_winstreak_price,
trophies_required_for_prestige,
)
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
def init(self) -> None:
super().init(title="Show Me Offers")
self.player_tag = add_text_field(
self,
"Brawl Stars Player Tag",
placeholder="#ABC123XYZ",
required=True,
max_length=15,
)

async def on_submit(self, interaction: discord.Interaction) -> None:
    await _handle_tag_submission(interaction, self.player_tag.value)

class RankedOrderModal(ui.Modal):
def init(
self,
player_tag: str,
current_rank: str,
p11_brawler_count: int,
) -> None:
super().init(title="Ranked Push")

    self.player_tag = player_tag
    self.current_rank = current_rank
    self.p11_brawler_count = p11_brawler_count

    self.desired_rank = add_text_field(
        self,
        "Desired Rank",
        placeholder="Mythic II / Legendary III / Masters I / Pro",
        required=True,
        max_length=30,
    )

async def on_submit(self, interaction: discord.Interaction) -> None:
    desired_rank = self.desired_rank.value.strip()

    price = calculate_rank_price(
        self.current_rank,
        desired_rank,
        p11_brawler_count=self.p11_brawler_count,
        is_duo_carry=False,
    )

    if price is None:
        await interaction.response.send_message(
            "Invalid desired rank. Make sure the desired rank is higher than your current rank.",
            ephemeral=True,
        )
        return

    normalized_desired_rank = _normalize_rank_for_display(desired_rank)

    await _create_offer_ticket(
        interaction,
        order_type="Ranked Push",
        slug="ranked-custom",
        summary_lines=[
            f"**Player Tag** — {self.player_tag}",
            f"**Current Rank** — {self.current_rank}",
            f"**Desired Rank** — {normalized_desired_rank}",
            f"**Power 11 Brawlers** — {self.p11_brawler_count}",
            f"**Price** — {price.formatted(CURRENCY_SYMBOL)}",
        ],
        extra={
            "price": price.final_price,
            "payment_method": None,
            "player_tag": self.player_tag,
            "current_rank": self.current_rank,
            "desired_rank": normalized_desired_rank,
            "p11_brawler_count": self.p11_brawler_count,
            "pricing_notes": price.notes,
        },
    )

async def _handle_show_offers(interaction: discord.Interaction) -> None:
await interaction.response.send_modal(WelcomeTagModal())

def welcome_panel_callbacks() -> CallbackMap:
return {"welcome_show_offers": _handle_show_offers}

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
) -> None:
await interaction.response.defer(thinking=True)

guild, opener = await _resolve_guild_and_member(interaction)

if guild is None or opener is None:
    await interaction.followup.send(
        "I couldn't confirm your membership in the server right now. Please try again shortly."
    )
    return

channel = await create_ticket_channel(
    guild,
    opener,
    order_type,
    slug,
    summary_lines,
    extra,
)

await interaction.followup.send(
    f"Done! Your ticket is ready: {channel.mention}"
)

async def _handle_tag_submission(
interaction: discord.Interaction,
raw_tag: str,
) -> None:
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

def _get_localized_name(value) -> str | None:
if isinstance(value, str):
return value

if isinstance(value, dict):
    for key in ("en", "EN", "english", "name"):
        candidate = value.get(key)
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()

    for candidate in value.values():
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()

return None

def _normalize_rank_for_display(raw_rank: str) -> str:
from utils.pricing import normalize_rank_input

normalized = normalize_rank_input(raw_rank)

if normalized is not None:
    return normalized

return raw_rank.strip()

def _get_rank_name(player: dict) -> str | None:
rank_name = _get_localized_name(player.get("rankedRankName"))

if rank_name:
    normalized = _normalize_rank_for_display(rank_name)

    if normalized != rank_name or normalized in (
        "Bronze I",
        "Bronze II",
        "Bronze III",
        "Silver I",
        "Silver II",
        "Silver III",
        "Gold I",
        "Gold II",
        "Gold III",
        "Diamond I",
        "Diamond II",
        "Diamond III",
        "Mythic I",
        "Mythic II",
        "Mythic III",
        "Legendary I",
        "Legendary II",
        "Legendary III",
        "Masters I",
        "Masters II",
        "Masters III",
        "Pro",
    ):
        return normalized

    return rank_name

rank_value = player.get("rankedRank")

if isinstance(rank_value, str):
    normalized = _normalize_rank_for_display(rank_value)

    if normalized:
        return normalized

return None

def _get_highest_win_streak(player: dict) -> tuple[int, str]:
highest_streak = 0
highest_brawler = "Unknown"

for brawler in player.get("brawlers", []):
    if not isinstance(brawler, dict):
        continue

    streak_value = brawler.get("maxWinStreak")

    if streak_value is None:
        streak_value = brawler.get("highestWinStreak")

    if streak_value is None:
        continue

    try:
        streak = int(streak_value)
    except (TypeError, ValueError):
        continue

    if streak > highest_streak:
        highest_streak = streak
        highest_brawler = brawler.get("name", "Unknown")

return highest_streak, highest_brawler

def _get_p11_brawler_count(player: dict) -> int:
count = 0

for brawler in player.get("brawlers", []):
    if not isinstance(brawler, dict):
        continue

    power = brawler.get("power", 0)

    try:
        if int(power) >= 11:
            count += 1
    except (TypeError, ValueError):
        continue

return count

def _build_offers_view(
player: dict,
tag: str,
) -> ui.LayoutView:
view = ui.LayoutView(timeout=None)

container = ui.Container(accent_color=ACCENT_COLOR)

container.add_item(
    ui.TextDisplay(
        f"# Offers for {player.get('name', 'you')}\n"
        "Pick whichever sounds good — one click opens a ticket."
    )
)

container.add_item(ui.Separator(visible=True))

victories = int(player.get("3vs3Victories", 0) or 0)

target_victories, victory_price = calculate_victory_milestone_price(
    victories
)

victory_section = ui.Section(
    ui.TextDisplay(
        f"**<:trophy:1479179772880748726> Victory Milestone**\n"
        f"You're at {victories:,} 3v3 Victories. "
        f"Reach {target_victories:,} for "
        f"{victory_price.formatted(CURRENCY_SYMBOL)}."
    ),
    accessory=ui.Button(
        style=discord.ButtonStyle.success,
        label="Order This",
        custom_id="welcome_order_victories",
    ),
)

async def on_order_victories(
    interaction: discord.Interaction,
) -> None:
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
        extra={
            "price": victory_price.final_price,
            "payment_method": None,
            "player_tag": tag,
        },
    )

victory_section.accessory.callback = on_order_victories

container.add_item(victory_section)
container.add_item(ui.Separator(visible=True))

prestige_threshold = trophies_required_for_prestige(3)

prestige_brawler = find_closest_brawler_below_threshold(
    player,
    prestige_threshold,
)

if prestige_brawler is not None:
    brawler_name = prestige_brawler.get("name", "Unknown")
    brawler_trophies = prestige_brawler.get("trophies", 0)

    prestige_price = calculate_prestige_price(
        brawler_trophies,
        3,
        is_duo_carry=False,
    )

    if prestige_price is not None:
        prestige_section = ui.Section(
            ui.TextDisplay(
                f"**<:p3:1479932740072767713> Prestige Push**\n"
                f"{brawler_name} is at {brawler_trophies:,} trophies — "
                f"your closest brawler to Prestige 3 "
                f"({prestige_threshold:,}). Get there for "
                f"{prestige_price.formatted(CURRENCY_SYMBOL)}."
            ),
            accessory=ui.Button(
                style=discord.ButtonStyle.success,
                label="Order This",
                custom_id="welcome_order_prestige",
            ),
        )

        async def on_order_prestige(
            interaction: discord.Interaction,
        ) -> None:
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

highest_streak, streak_brawler = _get_highest_win_streak(player)

target_winstreak, winstreak_price = calculate_winstreak_price(
    highest_streak
)

winstreak_section = ui.Section(
    ui.TextDisplay(
        f"**🔥 Winstreak Boost**\n"
        f"Your highest detected winstreak is **{highest_streak}** "
        f"on **{streak_brawler}**.\n"
        f"Get **{target_winstreak} winstreak on any brawler** "
        f"for **{winstreak_price.formatted(CURRENCY_SYMBOL)}**."
    ),
    accessory=ui.Button(
        style=discord.ButtonStyle.success,
        label="Order This",
        custom_id="welcome_order_winstreak",
    ),
)

async def on_order_winstreak(
    interaction: discord.Interaction,
) -> None:
    await _create_offer_ticket(
        interaction,
        order_type="Winstreak Boost",
        slug="winstreak-boost",
        summary_lines=[
            f"**Player Tag** — {tag}",
            f"**Highest Detected Winstreak** — {highest_streak}",
            f"**Recorded On** — {streak_brawler}",
            f"**Target Winstreak** — {target_winstreak}",
            f"**Price** — {winstreak_price.formatted(CURRENCY_SYMBOL)}",
        ],
        extra={
            "price": winstreak_price.final_price,
            "payment_method": None,
            "player_tag": tag,
            "highest_winstreak": highest_streak,
            "target_winstreak": target_winstreak,
            "record_brawler": streak_brawler,
        },
    )

winstreak_section.accessory.callback = on_order_winstreak

container.add_item(winstreak_section)
container.add_item(ui.Separator(visible=True))

ranked_rank_name = _get_rank_name(player)
p11_brawler_count = _get_p11_brawler_count(player)

if ranked_rank_name is not None:
    ranked_section = ui.Section(
        ui.TextDisplay(
            f"**<:pro:1449802988364366002> Ranked Push**\n"
            f"Your current Ranked tier is **{ranked_rank_name}**.\n"
            "Choose your desired rank to receive an automatic quote."
        ),
        accessory=ui.Button(
            style=discord.ButtonStyle.secondary,
            label="Get Quote",
            custom_id="welcome_order_ranked",
        ),
    )

    async def on_order_ranked(
        interaction: discord.Interaction,
    ) -> None:
        await interaction.response.send_modal(
            RankedOrderModal(
                player_tag=tag,
                current_rank=ranked_rank_name,
                p11_brawler_count=p11_brawler_count,
            )
        )

    ranked_section.accessory.callback = on_order_ranked

    container.add_item(ranked_section)
else:
    ranked_section = ui.Section(
        ui.TextDisplay(
            "**<:pro:1449802988364366002> Ranked Push**\n"
            "We couldn't determine your current Ranked tier automatically. "
            "Open a ticket and staff will confirm your rank and quote."
        ),
        accessory=ui.Button(
            style=discord.ButtonStyle.secondary,
            label="Ask About Ranked",
            custom_id="welcome_order_ranked",
        ),
    )

    async def on_order_ranked(
        interaction: discord.Interaction,
    ) -> None:
        await _create_offer_ticket(
            interaction,
            order_type="Ranked Push",
            slug="ranked-custom",
            summary_lines=[
                f"**Player Tag** — {tag}",
                "**Current Rank** — To be confirmed",
                "**Desired Rank** — To be confirmed",
                f"**Power 11 Brawlers** — {p11_brawler_count}",
                "**Price** — To be confirmed by staff",
            ],
            extra={
                "price": None,
                "payment_method": None,
                "player_tag": tag,
                "p11_brawler_count": p11_brawler_count,
            },
        )

    ranked_section.accessory.callback = on_order_ranked

    container.add_item(ranked_section)

view.add_item(container)

return view
