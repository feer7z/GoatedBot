from __future__ import annotations

import asyncio
import json

import discord
from discord import ui

from config import (
    ACCENT_COLOR,
    DATA_DIR,
    EMBEDS_NO_COMMANDS_DIR,
    STAFF_ROLE_IDS,
    SUPPORT_CATEGORY_ID,
    SUPPORT_TICKETS_FILE,
)
from utils.layout_loader import CallbackMap, load_layout_view
from utils.modal_helpers import add_text_field
from utils.permissions import is_staff_member
from utils.text_utils import build_notice_view, sanitize_channel_part
from utils.ticket_actions import build_standalone_star_picker

_LOCK = asyncio.Lock()


def _ensure_store() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not SUPPORT_TICKETS_FILE.exists():
        SUPPORT_TICKETS_FILE.write_text("{}", encoding="utf-8")


def _read_all() -> dict:
    _ensure_store()
    raw_text = SUPPORT_TICKETS_FILE.read_text(encoding="utf-8")
    if not raw_text.strip():
        return {}
    return json.loads(raw_text)


def _write_all(data: dict) -> None:
    _ensure_store()
    SUPPORT_TICKETS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


async def _create_record(channel_id: int, record: dict) -> None:
    async with _LOCK:
        data = _read_all()
        data[str(channel_id)] = record
        _write_all(data)


async def _get_record(channel_id: int) -> dict | None:
    async with _LOCK:
        return _read_all().get(str(channel_id))


async def _update_record(channel_id: int, **fields) -> dict | None:
    async with _LOCK:
        data = _read_all()
        key = str(channel_id)
        if key not in data:
            return None
        data[key].update(fields)
        _write_all(data)
        return data[key]


async def _delete_record(channel_id: int) -> None:
    async with _LOCK:
        data = _read_all()
        data.pop(str(channel_id), None)
        _write_all(data)


class SupportTicketModal(ui.Modal):
    def __init__(self) -> None:
        super().__init__(title="Open a Support Ticket")
        self.topic = add_text_field(
            self,
            "What do you need help with?",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=300,
        )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        channel = await create_support_ticket(interaction, self.topic.value)
        await interaction.followup.send(f"Your support ticket has been created: {channel.mention}", ephemeral=True)


async def create_support_ticket(interaction: discord.Interaction, topic: str) -> discord.TextChannel:
    guild = interaction.guild
    opener = interaction.user
    if guild is None or not isinstance(opener, discord.Member):
        raise RuntimeError("Support ticket creation requires a guild context.")

    category = None
    if SUPPORT_CATEGORY_ID is not None:
        maybe_category = guild.get_channel(SUPPORT_CATEGORY_ID)
        if isinstance(maybe_category, discord.CategoryChannel):
            category = maybe_category

    overwrites: dict[discord.Role | discord.Member, discord.PermissionOverwrite] = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        opener: discord.PermissionOverwrite(
            view_channel=True, send_messages=True, read_message_history=True, attach_files=True,
        ),
    }
    if guild.me is not None:
        overwrites[guild.me] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            manage_channels=True,
            embed_links=True,
        )
    for role_id in STAFF_ROLE_IDS:
        role = guild.get_role(role_id)
        if role is not None:
            overwrites[role] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True, manage_messages=True,
            )

    channel_name = f"support-{sanitize_channel_part(opener.display_name)}"[:95]
    channel = await guild.create_text_channel(
        name=channel_name,
        category=category,
        overwrites=overwrites,
        reason=f"Support ticket opened by {opener}",
    )

    await _create_record(
        channel.id,
        {"opener_id": opener.id, "topic": topic, "claimed_by": None, "status": "open"},
    )

    welcome_view = load_layout_view(
        EMBEDS_NO_COMMANDS_DIR / "support_welcome.json",
        values={"opener_mention": opener.mention, "topic": topic},
        callbacks=support_ticket_callbacks(),
        timeout=None,
    )
    await channel.send(view=welcome_view, allowed_mentions=discord.AllowedMentions(users=True))
    return channel


async def _handle_support_open(interaction: discord.Interaction) -> None:
    await interaction.response.send_modal(SupportTicketModal())


async def _handle_support_claim(interaction: discord.Interaction) -> None:
    member = interaction.user
    if not isinstance(member, discord.Member) or not is_staff_member(member):
        await interaction.response.send_message("Only staff can claim a ticket.", ephemeral=True)
        return

    channel = interaction.channel
    if not isinstance(channel, discord.TextChannel):
        return

    record = await _get_record(channel.id)
    if record is not None and record.get("claimed_by"):
        await interaction.response.send_message("This ticket has already been claimed.", ephemeral=True)
        return

    await _update_record(channel.id, claimed_by=member.id)
    await interaction.response.send_message(
        f"{member.mention} has claimed this ticket and will be helping you out.",
        allowed_mentions=discord.AllowedMentions(users=False),
    )


async def _send_satisfaction_survey(client: discord.Client, guild: discord.Guild, record: dict) -> None:
    opener_id = record["opener_id"]
    opener = guild.get_member(opener_id)
    target: discord.abc.Messageable | None = opener
    if target is None:
        try:
            target = await client.fetch_user(opener_id)
        except discord.NotFound:
            target = None
    if target is None:
        return

    topic = record.get("topic", "your support ticket")
    try:
        await target.send(
            f"Your Goated Boost support ticket (\"{topic}\") was just closed. We'd love a quick rating!",
        )
        await target.send(view=build_standalone_star_picker(opener_id, "Support", guild=guild))
    except discord.Forbidden:
        pass


async def _handle_support_close(interaction: discord.Interaction) -> None:
    channel = interaction.channel
    if not isinstance(channel, discord.TextChannel) or channel.guild is None:
        return

    record = await _get_record(channel.id)
    member = interaction.user
    is_opener = record is not None and member.id == record.get("opener_id")
    is_staff = isinstance(member, discord.Member) and is_staff_member(member)

    if not (is_opener or is_staff):
        await interaction.response.send_message(
            "Only the ticket opener or staff can close this ticket.", ephemeral=True,
        )
        return

    guild = channel.guild

    async def on_confirm(confirm_interaction: discord.Interaction) -> None:
        await confirm_interaction.response.edit_message(
            view=build_notice_view("Closing this ticket and sending a quick survey..."),
        )
        if record is not None:
            await _send_satisfaction_survey(confirm_interaction.client, guild, record)
        await _delete_record(channel.id)
        await asyncio.sleep(5)
        await channel.delete(reason=f"Support ticket closed by {confirm_interaction.user}")

    async def on_cancel(cancel_interaction: discord.Interaction) -> None:
        await cancel_interaction.response.edit_message(view=build_notice_view("Close cancelled."))

    view = ui.LayoutView(timeout=60)
    container = ui.Container(accent_color=ACCENT_COLOR)
    container.add_item(ui.TextDisplay("Are you sure you want to close this ticket? This cannot be undone."))
    row = ui.ActionRow()
    confirm_button = ui.Button(style=discord.ButtonStyle.danger, label="Close Ticket", custom_id="support_close_confirm")
    confirm_button.callback = on_confirm
    cancel_button = ui.Button(style=discord.ButtonStyle.secondary, label="Cancel", custom_id="support_close_cancel")
    cancel_button.callback = on_cancel
    row.add_item(confirm_button)
    row.add_item(cancel_button)
    container.add_item(row)
    view.add_item(container)

    await interaction.response.send_message(view=view, ephemeral=True)


def support_panel_callbacks() -> CallbackMap:
    return {"support_open_ticket": _handle_support_open}


def support_ticket_callbacks() -> CallbackMap:
    return {"support_claim": _handle_support_claim, "support_close": _handle_support_close}
