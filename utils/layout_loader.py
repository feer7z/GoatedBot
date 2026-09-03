from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Awaitable, Callable

import discord
from discord import ui

PLACEHOLDER_PATTERN = re.compile(r"\{\{(\w+)\}\}")

InteractionCallback = Callable[[discord.Interaction], Awaitable[None]]
CallbackMap = dict[str, InteractionCallback]


def _render_string(raw_text: str, values: dict[str, Any]) -> str:
    def _replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key in values:
            return str(values[key])
        return match.group(0)

    return PLACEHOLDER_PATTERN.sub(_replace, raw_text)


def render_placeholders(node: Any, values: dict[str, Any]) -> Any:
    if isinstance(node, str):
        return _render_string(node, values)
    if isinstance(node, list):
        return [render_placeholders(child, values) for child in node]
    if isinstance(node, dict):
        return {key: render_placeholders(child, values) for key, child in node.items()}
    return node


def load_layout_dict(path: str | Path, values: dict[str, Any] | None = None) -> dict:
    raw_text = Path(path).read_text(encoding="utf-8")
    layout = json.loads(raw_text)
    if values:
        layout = render_placeholders(layout, values)
    return layout


def _parse_emoji(raw_emoji: Any) -> str | None:
    if not raw_emoji:
        return None
    if isinstance(raw_emoji, str):
        return raw_emoji
    if isinstance(raw_emoji, dict):
        name = raw_emoji.get("name")
        emoji_id = raw_emoji.get("id")
        if emoji_id:
            animated = raw_emoji.get("animated", False)
            prefix = "a" if animated else ""
            return f"<{prefix}:{name}:{emoji_id}>"
        return name
    return None


def _build_button(data: dict, callbacks: CallbackMap) -> ui.Button:
    button = ui.Button(
        style=discord.ButtonStyle(data.get("style", 2)),
        label=data.get("label"),
        custom_id=data.get("custom_id"),
        url=data.get("url"),
        disabled=data.get("disabled", False),
        emoji=_parse_emoji(data.get("emoji")),
    )
    custom_id = data.get("custom_id")
    if custom_id and custom_id in callbacks:
        button.callback = callbacks[custom_id]
    return button


def _build_select(data: dict, callbacks: CallbackMap) -> ui.Select:
    options = [
        discord.SelectOption(
            label=option["label"],
            value=option["value"],
            description=option.get("description"),
            emoji=_parse_emoji(option.get("emoji")),
            default=option.get("default", False),
        )
        for option in data.get("options", [])
    ]
    select = ui.Select(
        custom_id=data["custom_id"],
        placeholder=data.get("placeholder"),
        min_values=data.get("min_values", 1),
        max_values=data.get("max_values", 1),
        options=options,
        disabled=data.get("disabled", False),
    )
    custom_id = data.get("custom_id")
    if custom_id and custom_id in callbacks:
        select.callback = callbacks[custom_id]
    return select


def _build_text_display(data: dict) -> ui.TextDisplay:
    return ui.TextDisplay(data.get("content", ""))


def _build_separator(data: dict) -> ui.Separator:
    return ui.Separator(
        visible=data.get("divider", True),
        spacing=discord.SeparatorSpacing(data.get("spacing", 1)),
    )


def _build_thumbnail(data: dict) -> ui.Thumbnail:
    media = data.get("media", {})
    media_url = media.get("url", "") if isinstance(media, dict) else str(media)
    return ui.Thumbnail(
        media=media_url,
        description=data.get("description"),
        spoiler=data.get("spoiler", False),
    )


def _build_media_gallery(data: dict) -> ui.MediaGallery:
    gallery_items = []
    for item in data.get("items", []):
        media = item.get("media", {})
        media_url = media.get("url", "") if isinstance(media, dict) else str(media)
        gallery_items.append(
            discord.MediaGalleryItem(
                media=media_url,
                description=item.get("description"),
                spoiler=item.get("spoiler", False),
            )
        )
    return ui.MediaGallery(*gallery_items)


def _build_action_row(data: dict, callbacks: CallbackMap) -> ui.ActionRow:
    row = ui.ActionRow()
    for child in data.get("components", []):
        item = build_component(child, callbacks)
        if item is not None:
            row.add_item(item)
    return row


def _build_section(data: dict, callbacks: CallbackMap) -> ui.Section:
    accessory_data = data.get("accessory")
    if accessory_data is None:
        raise ValueError("A Section component requires an 'accessory' entry.")
    accessory = build_component(accessory_data, callbacks)
    section = ui.Section(accessory=accessory)
    for child in data.get("components", []):
        item = build_component(child, callbacks)
        if item is not None:
            section.add_item(item)
    return section


def _build_container(data: dict, callbacks: CallbackMap) -> ui.Container:
    container = ui.Container(
        accent_color=data.get("accent_color"),
        spoiler=data.get("spoiler", False),
    )
    for child in data.get("components", []):
        item = build_component(child, callbacks)
        if item is not None:
            container.add_item(item)
    return container


_COMPONENT_TYPE_ACTION_ROW = 1
_COMPONENT_TYPE_BUTTON = 2
_COMPONENT_TYPE_SELECT = 3
_COMPONENT_TYPE_SECTION = 9
_COMPONENT_TYPE_TEXT_DISPLAY = 10
_COMPONENT_TYPE_THUMBNAIL = 11
_COMPONENT_TYPE_MEDIA_GALLERY = 12
_COMPONENT_TYPE_SEPARATOR = 14
_COMPONENT_TYPE_CONTAINER = 17


def build_component(data: dict, callbacks: CallbackMap) -> Any:
    component_type = data.get("type")
    if component_type == _COMPONENT_TYPE_ACTION_ROW:
        return _build_action_row(data, callbacks)
    if component_type == _COMPONENT_TYPE_BUTTON:
        return _build_button(data, callbacks)
    if component_type == _COMPONENT_TYPE_SELECT:
        return _build_select(data, callbacks)
    if component_type == _COMPONENT_TYPE_SECTION:
        return _build_section(data, callbacks)
    if component_type == _COMPONENT_TYPE_TEXT_DISPLAY:
        return _build_text_display(data)
    if component_type == _COMPONENT_TYPE_THUMBNAIL:
        return _build_thumbnail(data)
    if component_type == _COMPONENT_TYPE_MEDIA_GALLERY:
        return _build_media_gallery(data)
    if component_type == _COMPONENT_TYPE_SEPARATOR:
        return _build_separator(data)
    if component_type == _COMPONENT_TYPE_CONTAINER:
        return _build_container(data, callbacks)
    return None


def build_layout_view(
    layout: dict,
    callbacks: CallbackMap | None = None,
    timeout: float | None = None,
) -> ui.LayoutView:
    resolved_callbacks = callbacks or {}
    view = ui.LayoutView(timeout=timeout)
    for component_data in layout.get("components", []):
        item = build_component(component_data, resolved_callbacks)
        if item is not None:
            view.add_item(item)
    return view


def load_layout_view(
    path: str | Path,
    values: dict[str, Any] | None = None,
    callbacks: CallbackMap | None = None,
    timeout: float | None = None,
) -> ui.LayoutView:
    layout = load_layout_dict(path, values)
    return build_layout_view(layout, callbacks, timeout)
