from __future__ import annotations

import asyncio
import io
import re

import discord
from discord import ui

from config import (
    ACCENT_COLOR,
    BOOSTER_ROLE_ID,
    CLIENT_ROLE_ID,
    COMPLETED_CHANNEL_ID,
    EMBEDS_NO_COMMANDS_DIR,
    REVIEWS_CHANNEL_ID,
    STAFF_ROLE_IDS,
    TICKET_CATEGORY_ID,
)
from utils import storage
from utils.layout_loader import CallbackMap, load_layout_view
from utils.modal_helpers import add_text_field
from utils.permissions import is_staff_member, member_has_role
from utils.watermark import WatermarkError, apply_watermark


def _sanitize_channel_part(raw_value: str) -> str:
    lowered = raw_value.strip().lower()
    lowered = re.sub(r"[^a-z0-9]+", "-", lowered)
    lowered = lowered.strip("-")
    return lowered or "user"


def _simple_notice_view(content: str) -> ui.LayoutView:
    view = ui.LayoutView(timeout=None)
    container = ui.Container(accent_color=ACCENT_COLOR)
    container.add_item(ui.TextDisplay(content))
    view.add_item(container)
    return view


async def create_ticket_channel(
    interaction: discord.Interaction,
    order_type: str,
    order_type_slug: str,
    summary_lines: list[str],
) -> discord.TextChannel:
    guild = interaction.guild
    opener = interaction.user
    if guild is None or not isinstance(opener, discord.Member):
        raise RuntimeError("Ticket creation requires a guild context.")

    category = None
    if TICKET_CATEGORY_ID is not None:
        maybe_category = guild.get_channel(TICKET_CATEGORY_ID)
        if isinstance(maybe_category, discord.CategoryChannel):
            category = maybe_category

    overwrites: dict[discord.Role | discord.Member, discord.PermissionOverwrite] = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        opener: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            attach_files=True,
        ),
    }
    if guild.me is not None:
        overwrites[guild.me] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            manage_channels=True,
            embed_links=True,
            attach_files=True,
        )

    booster_role = guild.get_role(BOOSTER_ROLE_ID)
    if booster_role is not None:
        overwrites[booster_role] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
        )

    for role_id in STAFF_ROLE_IDS:
        role = guild.get_role(role_id)
        if role is not None:
            overwrites[role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_messages=True,
            )

    channel_name = f"ticket-{_sanitize_channel_part(opener.name)}"[:95]

    channel = await guild.create_text_channel(
        name=channel_name,
        category=category,
        overwrites=overwrites,
        reason=f"Order ticket opened by {opener} for {order_type}",
    )

    await storage.create_ticket(
        channel.id,
        {
            "opener_id": opener.id,
            "order_type": order_type,
            "status": "open",
            "paid": False,
            "claimed_by": None,
        },
    )

    summary_block = "\n".join(summary_lines)
    welcome_view = load_layout_view(
        EMBEDS_NO_COMMANDS_DIR / "ticket_welcome.json",
        values={
            "opener_mention": opener.mention,
            "booster_mention": booster_role.mention if booster_role else "the booster team",
            "summary_block": summary_block,
        },
        callbacks=ticket_welcome_callbacks(),
        timeout=None,
    )

    await channel.send(
        view=welcome_view,
        allowed_mentions=discord.AllowedMentions(roles=True, users=True, everyone=False),
    )

    return channel


async def send_order_confirmation(
    interaction: discord.Interaction,
    order_type: str,
    order_type_slug: str,
    summary_lines: list[str],
) -> None:
    summary_block = "\n".join(summary_lines)

    async def on_confirm(confirm_interaction: discord.Interaction) -> None:
        await confirm_interaction.response.defer(ephemeral=True, thinking=True)
        channel = await create_ticket_channel(confirm_interaction, order_type, order_type_slug, summary_lines)
        await confirm_interaction.followup.send(f"Your ticket has been created: {channel.mention}", ephemeral=True)

    async def on_cancel(cancel_interaction: discord.Interaction) -> None:
        await cancel_interaction.response.edit_message(
            view=_simple_notice_view("Order cancelled. Feel free to start a new order any time."),
        )

    view = load_layout_view(
        EMBEDS_NO_COMMANDS_DIR / "confirmation.json",
        values={"summary_block": summary_block},
        callbacks={"confirm_order": on_confirm, "cancel_order": on_cancel},
        timeout=300,
    )

    if interaction.response.is_done():
        await interaction.followup.send(view=view, ephemeral=True)
    else:
        await interaction.response.send_message(view=view, ephemeral=True)


async def _handle_ticket_close(interaction: discord.Interaction) -> None:
    async def on_confirm(confirm_interaction: discord.Interaction) -> None:
        channel = confirm_interaction.channel
        await confirm_interaction.response.edit_message(
            view=_simple_notice_view("Closing this ticket in a few seconds..."),
        )
        if isinstance(channel, discord.TextChannel):
            await storage.delete_ticket(channel.id)
            await asyncio.sleep(5)
            await channel.delete(reason=f"Ticket closed by {confirm_interaction.user}")

    async def on_cancel(cancel_interaction: discord.Interaction) -> None:
        await cancel_interaction.response.edit_message(view=_simple_notice_view("Close cancelled."))

    view = ui.LayoutView(timeout=60)
    container = ui.Container(accent_color=ACCENT_COLOR)
    container.add_item(ui.TextDisplay("Are you sure you want to close this ticket? This cannot be undone."))
    row = ui.ActionRow()
    confirm_button = ui.Button(style=discord.ButtonStyle.danger, label="Close Ticket", custom_id="ticket_close_confirm")
    confirm_button.callback = on_confirm
    cancel_button = ui.Button(style=discord.ButtonStyle.secondary, label="Cancel", custom_id="ticket_close_cancel")
    cancel_button.callback = on_cancel
    row.add_item(confirm_button)
    row.add_item(cancel_button)
    container.add_item(row)
    view.add_item(container)

    await interaction.response.send_message(view=view, ephemeral=True)


async def _handle_ticket_paid(interaction: discord.Interaction) -> None:
    member = interaction.user
    if not isinstance(member, discord.Member) or not is_staff_member(member):
        await interaction.response.send_message("Only staff can mark a ticket as paid.", ephemeral=True)
        return

    channel = interaction.channel
    if not isinstance(channel, discord.TextChannel):
        return

    ticket = await storage.get_ticket(channel.id)
    if ticket is None:
        await interaction.response.send_message("This channel is not a tracked ticket.", ephemeral=True)
        return

    await storage.update_ticket(channel.id, paid=True)

    guild = interaction.guild
    booster_role = guild.get_role(BOOSTER_ROLE_ID) if guild else None

    view = load_layout_view(
        EMBEDS_NO_COMMANDS_DIR / "paid.json",
        values={"booster_mention": booster_role.mention if booster_role else "the booster team"},
        callbacks=paid_callbacks(),
        timeout=None,
    )
    await interaction.response.send_message(
        view=view,
        allowed_mentions=discord.AllowedMentions(roles=True, everyone=False),
    )


async def _handle_ticket_completed(interaction: discord.Interaction) -> None:
    member = interaction.user
    if not isinstance(member, discord.Member) or not is_staff_member(member):
        await interaction.response.send_message("Only staff can mark a ticket as completed.", ephemeral=True)
        return

    channel = interaction.channel
    if not isinstance(channel, discord.TextChannel):
        return

    ticket = await storage.get_ticket(channel.id)
    if ticket is None:
        await interaction.response.send_message("This channel is not a tracked ticket.", ephemeral=True)
        return

    await storage.update_ticket(channel.id, status="awaiting_screenshot")

    guild = interaction.guild
    opener = guild.get_member(ticket["opener_id"]) if guild else None
    opener_mention = opener.mention if opener else "the client"

    view = load_layout_view(
        EMBEDS_NO_COMMANDS_DIR / "awaiting_screenshot.json",
        values={"opener_mention": opener_mention},
        timeout=None,
    )
    await interaction.response.send_message(
        view=view,
        allowed_mentions=discord.AllowedMentions(users=True),
    )


async def _handle_ticket_call_booster(interaction: discord.Interaction) -> None:
    member = interaction.user
    if not isinstance(member, discord.Member) or not is_staff_member(member):
        await interaction.response.send_message("Only staff can call a booster.", ephemeral=True)
        return

    guild = interaction.guild
    booster_role = guild.get_role(BOOSTER_ROLE_ID) if guild else None
    mention = booster_role.mention if booster_role else "the booster team"

    await interaction.response.send_message(
        view=_simple_notice_view(f"{mention} — assistance requested on this ticket."),
        allowed_mentions=discord.AllowedMentions(roles=True, everyone=False),
    )


def ticket_welcome_callbacks() -> CallbackMap:
    return {
        "ticket_close": _handle_ticket_close,
        "ticket_paid": _handle_ticket_paid,
        "ticket_completed": _handle_ticket_completed,
        "ticket_call_booster": _handle_ticket_call_booster,
    }


async def _handle_ticket_accept_job(interaction: discord.Interaction) -> None:
    member = interaction.user
    if not isinstance(member, discord.Member) or not member_has_role(member, BOOSTER_ROLE_ID):
        await interaction.response.send_message("Only boosters can accept this job.", ephemeral=True)
        return

    channel = interaction.channel
    if not isinstance(channel, discord.TextChannel):
        return

    ticket = await storage.get_ticket(channel.id)
    if ticket is not None and ticket.get("claimed_by"):
        await interaction.response.send_message("This job has already been accepted by another booster.", ephemeral=True)
        return

    await storage.update_ticket(channel.id, claimed_by=member.id)

    await interaction.response.edit_message(
        view=_simple_notice_view(f"## Job Accepted\n{member.mention} is now working on this order."),
    )


def paid_callbacks() -> CallbackMap:
    return {"ticket_accept_job": _handle_ticket_accept_job}


async def process_completion_screenshot(message: discord.Message) -> None:
    if message.guild is None or not isinstance(message.channel, discord.TextChannel):
        return

    ticket = await storage.get_ticket(message.channel.id)
    if ticket is None or ticket.get("status") != "awaiting_screenshot":
        return
    if message.author.id != ticket.get("opener_id"):
        return

    image_attachment = next(
        (attachment for attachment in message.attachments if (attachment.content_type or "").startswith("image/")),
        None,
    )
    if image_attachment is None:
        return

    try:
        source_bytes = await image_attachment.read()
        watermarked_bytes = apply_watermark(source_bytes)
    except WatermarkError as error:
        await message.channel.send(f"Could not process the screenshot: {error}")
        return
    except Exception:
        await message.channel.send("Could not process that image. Please try uploading it again.")
        return

    order_type = ticket.get("order_type", "Boost")
    opener = message.guild.get_member(ticket["opener_id"])
    opener_mention = opener.mention if opener else message.author.mention

    completed_channel = message.guild.get_channel(COMPLETED_CHANNEL_ID)
    if isinstance(completed_channel, discord.TextChannel):
        completed_view = load_layout_view(
            EMBEDS_NO_COMMANDS_DIR / "completed_post.json",
            values={"client_mention": opener_mention, "order_type": order_type},
            timeout=None,
        )
        await completed_channel.send(
            view=completed_view,
            file=discord.File(io.BytesIO(watermarked_bytes), filename="completed.png"),
            allowed_mentions=discord.AllowedMentions(users=True),
        )

    if opener is not None:
        client_role = message.guild.get_role(CLIENT_ROLE_ID)
        if client_role is not None:
            try:
                await opener.add_roles(client_role, reason="Completed a Goated Boost order")
            except discord.Forbidden:
                pass

    await storage.update_ticket(message.channel.id, status="completed")

    review_view = load_layout_view(
        EMBEDS_NO_COMMANDS_DIR / "review_prompt.json",
        values={"opener_mention": opener_mention},
        callbacks=review_prompt_callbacks(),
        timeout=None,
    )
    await message.channel.send(
        view=review_view,
        allowed_mentions=discord.AllowedMentions(users=True),
    )
    await message.reply("Thanks! Your screenshot has been posted.", mention_author=False)


class ReviewCommentModal(ui.Modal):
    def __init__(self, stars: int, order_type: str, opener_id: int) -> None:
        super().__init__(title=f"Rate {stars} / 5 Stars")
        self.stars = stars
        self.order_type = order_type
        self.opener_id = opener_id
        self.comment = add_text_field(
            self,
            "Comment (optional)",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=500,
        )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await _submit_review(interaction, self.stars, self.order_type, self.opener_id, self.comment.value)


async def _handle_review_rate(interaction: discord.Interaction, stars: int) -> None:
    channel = interaction.channel
    ticket = await storage.get_ticket(channel.id) if isinstance(channel, discord.TextChannel) else None
    order_type = ticket.get("order_type", "Boost") if ticket else "Boost"
    opener_id = ticket.get("opener_id", interaction.user.id) if ticket else interaction.user.id

    if interaction.user.id != opener_id:
        await interaction.response.send_message(
            "Only the client who opened this ticket can leave a review.", ephemeral=True,
        )
        return

    await interaction.response.send_modal(ReviewCommentModal(stars, order_type, opener_id))


async def _submit_review(
    interaction: discord.Interaction,
    stars: int,
    order_type: str,
    opener_id: int,
    comment: str,
) -> None:
    guild = interaction.guild
    reviews_channel = guild.get_channel(REVIEWS_CHANNEL_ID) if guild else None

    stars_display = "★" * stars + "☆" * (5 - stars)
    comment_block = comment.strip() if comment and comment.strip() else "_No comment left._"

    if isinstance(reviews_channel, discord.TextChannel):
        review_view = load_layout_view(
            EMBEDS_NO_COMMANDS_DIR / "review_result.json",
            values={
                "reviewer_mention": f"<@{opener_id}>",
                "order_type": order_type,
                "stars_display": stars_display,
                "comment_block": comment_block,
            },
            timeout=None,
        )
        await reviews_channel.send(
            view=review_view,
            allowed_mentions=discord.AllowedMentions(users=False),
        )

    await interaction.response.send_message("Thanks for your feedback!", ephemeral=True)


def review_prompt_callbacks() -> CallbackMap:
    callbacks: CallbackMap = {}
    for stars in range(6):
        async def handler(interaction: discord.Interaction, stars: int = stars) -> None:
            await _handle_review_rate(interaction, stars)

        callbacks[f"review_rate_{stars}"] = handler
    return callbacks
