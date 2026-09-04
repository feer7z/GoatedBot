from __future__ import annotations

import re

from discord import ui

from config import ACCENT_COLOR


def sanitize_channel_part(raw_value: str) -> str:
    lowered = raw_value.strip().lower()
    lowered = re.sub(r"[^a-z0-9]+", "-", lowered)
    lowered = lowered.strip("-")
    return lowered or "user"


def build_notice_view(content: str) -> ui.LayoutView:
    view = ui.LayoutView(timeout=None)
    container = ui.Container(accent_color=ACCENT_COLOR)
    container.add_item(ui.TextDisplay(content))
    view.add_item(container)
    return view
