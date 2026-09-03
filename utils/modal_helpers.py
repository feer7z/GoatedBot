from __future__ import annotations

import discord
from discord import ui


def add_text_field(
    modal: ui.Modal,
    label: str,
    *,
    style: discord.TextStyle = discord.TextStyle.short,
    placeholder: str | None = None,
    required: bool = True,
    max_length: int | None = None,
    default: str | None = None,
) -> ui.TextInput:
    text_input = ui.TextInput(
        style=style,
        placeholder=placeholder,
        required=required,
        max_length=max_length,
        default=default,
    )
    modal.add_item(ui.Label(text=label, component=text_input))
    return text_input
