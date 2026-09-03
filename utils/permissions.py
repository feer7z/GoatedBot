from __future__ import annotations

import discord
from discord import app_commands

from config import BOOSTER_ROLE_ID, STAFF_ROLE_IDS


def member_has_role(member: discord.Member, role_id: int) -> bool:
    return any(role.id == role_id for role in member.roles)


def is_staff_member(member: discord.Member) -> bool:
    if member.guild_permissions.administrator:
        return True
    return any(role.id in STAFF_ROLE_IDS for role in member.roles)


def is_booster_member(member: discord.Member) -> bool:
    return member_has_role(member, BOOSTER_ROLE_ID) or is_staff_member(member)


def staff_only():
    async def predicate(interaction: discord.Interaction) -> bool:
        if not isinstance(interaction.user, discord.Member):
            return False
        return is_staff_member(interaction.user)

    return app_commands.check(predicate)
