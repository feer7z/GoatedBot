from __future__ import annotations

import re
from dataclasses import dataclass, field

RANK_TIERS = [
    "Bronze I", "Bronze II", "Bronze III",
    "Silver I", "Silver II", "Silver III",
    "Gold I", "Gold II", "Gold III",
    "Diamond I", "Diamond II", "Diamond III",
    "Mythic I", "Mythic II", "Mythic III",
    "Legendary I", "Legendary II", "Legendary III",
    "Masters",
]

RANK_ALIASES = {
    # Bronze I
    "bronze1": "Bronze I",
    "bronze 1": "Bronze I",
    "bronzei": "Bronze I",
    "bronze i": "Bronze I",
    "bronce1": "Bronze I",
    "bronce 1": "Bronze I",
    "broncei": "Bronze I",
    "bronce i": "Bronze I",
    "bronse1": "Bronze I",
    "bronse 1": "Bronze I",

    # Bronze II
    "bronze2": "Bronze II",
    "bronze 2": "Bronze II",
    "bronzeii": "Bronze II",
    "bronze ii": "Bronze II",
    "bronce2": "Bronze II",
    "bronce 2": "Bronze II",
    "bronceii": "Bronze II",
    "bronce ii": "Bronze II",
    "bronse2": "Bronze II",
    "bronse 2": "Bronze II",

    # Bronze III
    "bronze3": "Bronze III",
    "bronze 3": "Bronze III",
    "bronzeiii": "Bronze III",
    "bronze iii": "Bronze III",
    "bronce3": "Bronze III",
    "bronce 3": "Bronze III",
    "bronceiii": "Bronze III",
    "bronce iii": "Bronze III",
    "bronse3": "Bronze III",
    "bronse 3": "Bronze III",

    # Silver I
    "silver1": "Silver I",
    "silver 1": "Silver I",
    "silveri": "Silver I",
    "silver i": "Silver I",
    "siver1": "Silver I",
    "siver 1": "Silver I",
    "silvr1": "Silver I",
    "silvr 1": "Silver I",
    "plata1": "Silver I",
    "plata 1": "Silver I",

    # Silver II
    "silver2": "Silver II",
    "silver 2": "Silver II",
    "silverii": "Silver II",
    "silver ii": "Silver II",
    "siver2": "Silver II",
    "siver 2": "Silver II",
    "silvr2": "Silver II",
    "silvr 2": "Silver II",
    "plata2": "Silver II",
    "plata 2": "Silver II",

    # Silver III
    "silver3": "Silver III",
    "silver 3": "Silver III",
    "silveriii": "Silver III",
    "silver iii": "Silver III",
    "siver3": "Silver III",
    "siver 3": "Silver III",
    "silvr3": "Silver III",
    "silvr 3": "Silver III",
    "plata3": "Silver III",
    "plata 3": "Silver III",

    # Gold I
    "gold1": "Gold I",
    "gold 1": "Gold I",
    "goldi": "Gold I",
    "gold i": "Gold I",
    "gld1": "Gold I",
    "gld 1": "Gold I",
    "oro1": "Gold I",
    "oro 1": "Gold I",

    # Gold II
    "gold2": "Gold II",
    "gold 2": "Gold II",
    "goldii": "Gold II",
    "gold ii": "Gold II",
    "gld2": "Gold II",
    "gld 2": "Gold II",
    "oro2": "Gold II",
    "oro 2": "Gold II",

    # Gold III
    "gold3": "Gold III",
    "gold 3": "Gold III",
    "goldiii": "Gold III",
    "gold iii": "Gold III",
    "gld3": "Gold III",
    "gld 3": "Gold III",
    "oro3": "Gold III",
    "oro 3": "Gold III",

    # Diamond I
    "diamond1": "Diamond I",
    "diamond 1": "Diamond I",
    "diamondi": "Diamond I",
    "diamond i": "Diamond I",
    "diamon1": "Diamond I",
    "diamon 1": "Diamond I",
    "diamante1": "Diamond I",
    "diamante 1": "Diamond I",

    # Diamond II
    "diamond2": "Diamond II",
    "diamond 2": "Diamond II",
    "diamondii": "Diamond II",
    "diamond ii": "Diamond II",
    "diamon2": "Diamond II",
    "diamon 2": "Diamond II",
    "diamante2": "Diamond II",
    "diamante 2": "Diamond II",

    # Diamond III
    "diamond3": "Diamond III",
    "diamond 3": "Diamond III",
    "diamondiii": "Diamond III",
    "diamond iii": "Diamond III",
    "diamon3": "Diamond III",
    "diamon 3": "Diamond III",
    "diamante3": "Diamond III",
    "diamante 3": "Diamond III",

    # Mythic I
    "mythic1": "Mythic I",
    "mythic 1": "Mythic I",
    "mythici": "Mythic I",
    "mythic i": "Mythic I",
    "mythyc1": "Mythic I",
    "mythyc 1": "Mythic I",
    "mitico1": "Mythic I",
    "mitico 1": "Mythic I",

    # Mythic II
    "mythic2": "Mythic II",
    "mythic 2": "Mythic II",
    "mythicii": "Mythic II",
    "mythic ii": "Mythic II",
    "mythyc2": "Mythic II",
    "mythyc 2": "Mythic II",
    "mitico2": "Mythic II",
    "mitico 2": "Mythic II",

    # Mythic III
    "mythic3": "Mythic III",
    "mythic 3": "Mythic III",
    "mythiciii": "Mythic III",
    "mythic iii": "Mythic III",
    "mythyc3": "Mythic III",
    "mythyc 3": "Mythic III",
    "mitico3": "Mythic III",
    "mitico 3": "Mythic III",

    # Legendary I
    "legendary1": "Legendary I",
    "legendary 1": "Legendary I",
    "legendaryi": "Legendary I",
    "legendary i": "Legendary I",
    "legend1": "Legendary I",
    "legend 1": "Legendary I",
    "legendario1": "Legendary I",
    "legendario 1": "Legendary I",

    # Legendary II
    "legendary2": "Legendary II",
    "legendary 2": "Legendary II",
    "legendaryii": "Legendary II",
    "legendary ii": "Legendary II",
    "legend2": "Legendary II",
    "legend 2": "Legendary II",
    "legendario2": "Legendary II",
    "legendario 2": "Legendary II",

    # Legendary III
    "legendary3": "Legendary III",
    "legendary 3": "Legendary III",
    "legendaryiii": "Legendary III",
    "legendary iii": "Legendary III",
    "legend3": "Legendary III",
    "legend 3": "Legendary III",
    "legendario3": "Legendary III",
    "legendario 3": "Legendary III",

    # Masters I
    "master1": "Masters I",
    "master 1": "Masters I",
    "masteri": "Masters I",
    "master i": "Masters I",
    "masters1": "Masters I",
    "masters 1": "Masters I",
    "mastersi": "Masters I",
    "masters i": "Masters I",
    "maestro1": "Masters I",
    "maestro 1": "Masters I",

    # Masters II
    "master2": "Masters II",
    "master 2": "Masters II",
    "masterii": "Masters II",
    "master ii": "Masters II",
    "masters2": "Masters II",
    "masters 2": "Masters II",
    "mastersii": "Masters II",
    "masters ii": "Masters II",
    "maestro2": "Masters II",
    "maestro 2": "Masters II",

    # Masters III
    "master3": "Masters III",
    "master 3": "Masters III",
    "masteriii": "Masters III",
    "master iii": "Masters III",
    "masters3": "Masters III",
    "masters 3": "Masters III",
    "mastersiii": "Masters III",
    "masters iii": "Masters III",
    "maestro3": "Masters III",
    "maestro 3": "Masters III",

    # Pro
    "pro": "Pro",
    "pros": "Pro",
    "pr0": "Pro",
    "proo": "Pro",
    "pr": "Pro",
}

PRICE_PER_RANK_STEP = 3.5

PRESTIGE_TROPHY_STEP = 1000
PRICE_PER_PRESTIGE_TROPHY = 0.05
PRESTIGE_DUO_MULTIPLIER = 1.5

P11_DISCOUNT_TIERS = [
    (70, 0.10),
    (60, 0.075),
    (50, 0.05),
    (40, 0.025),
]

MINIMUM_ORDER_PRICE = 5.0

OTHER_SERVICE_OPTIONS = [
    {
        "key": "matcherino_pin",
        "label": "Matcherino Pin",
        "description": "150€",
        "base_price": 150.0,
        "pricing_note": "Flat rate.",
        "detail_label": "Any notes for the booster (optional)",
    },
    {
        "key": "matcherino_tournament",
        "label": "Play Matcherino Tournament (tB+ team)",
        "description": "Custom quote",
        "base_price": None,
        "pricing_note": "Requires a tB+ team. Final price is confirmed by staff.",
        "detail_label": "Preferred date/time and team notes",
    },
    {
        "key": "championship_challenge",
        "label": "Championship Challenge — 15 Wins",
        "description": "5€",
        "base_price": 5.0,
        "pricing_note": "Flat rate.",
        "detail_label": "Any notes for the booster (optional)",
    },
    {
        "key": "winstreak_boost",
        "label": "Winstreak Boost",
        "description": "From 5€",
        "base_price": 5.0,
        "pricing_note": "Starting price. Scales with the requested streak length.",
        "detail_label": "Desired winstreak (e.g. 10)",
        "per_unit_price": 0.5,
    },
    {
        "key": "other_request",
        "label": "Other Request",
        "description": "Custom quote",
        "base_price": None,
        "pricing_note": "Final price is confirmed by staff after reviewing the details.",
        "detail_label": "Describe exactly what you need",
    },
]


def normalize_rank_input(raw_value: str) -> str | None:
    cleaned = raw_value.strip()
    if not cleaned:
        return None
    for tier in RANK_TIERS:
        if cleaned.lower() == tier.lower():
            return tier
    alias_key = cleaned.lower().replace("-", " ")
    alias_key_compact = alias_key.replace(" ", "")
    if alias_key in RANK_ALIASES:
        return RANK_ALIASES[alias_key]
    if alias_key_compact in RANK_ALIASES:
        return RANK_ALIASES[alias_key_compact]
    return None


def rank_distance(start_rank: str, desired_rank: str) -> int | None:
    if start_rank not in RANK_TIERS or desired_rank not in RANK_TIERS:
        return None
    distance = RANK_TIERS.index(desired_rank) - RANK_TIERS.index(start_rank)
    return distance


def p11_discount_rate(p11_brawler_count: int | None) -> float:
    if p11_brawler_count is None:
        return 0.0
    for threshold, discount in P11_DISCOUNT_TIERS:
        if p11_brawler_count >= threshold:
            return discount
    return 0.0


@dataclass
class PriceBreakdown:
    base_price: float
    discount_rate: float
    multiplier: float
    final_price: float
    notes: list[str] = field(default_factory=list)

    def formatted(self, symbol: str) -> str:
        return f"{self.final_price:.2f}{symbol}"


def calculate_rank_price(
    start_rank: str,
    desired_rank: str,
    p11_brawler_count: int | None = None,
    is_duo_carry: bool = False,
) -> PriceBreakdown | None:
    distance = rank_distance(start_rank, desired_rank)
    if distance is None or distance <= 0:
        return None

    base_price = distance * PRICE_PER_RANK_STEP
    discount_rate = p11_discount_rate(p11_brawler_count)
    multiplier = 1.0
    notes = []

    if is_duo_carry:
        notes.append("Rank carry (duo) — same base rate as a solo boost.")

    price_after_discount = base_price * (1 - discount_rate) * multiplier
    final_price = max(price_after_discount, MINIMUM_ORDER_PRICE)

    if discount_rate > 0:
        notes.append(f"{discount_rate * 100:g}% off applied for {p11_brawler_count}+ Power 11 brawlers.")

    return PriceBreakdown(
        base_price=base_price,
        discount_rate=discount_rate,
        multiplier=multiplier,
        final_price=round(final_price, 2),
        notes=notes,
    )


def parse_prestige_level(raw_value: str) -> int | None:
    cleaned = raw_value.strip().upper().replace(" ", "")
    match = re.fullmatch(r"P(\d{1,2})", cleaned)
    if match:
        return int(match.group(1))
    if cleaned.isdigit():
        return int(cleaned)
    return None


def current_prestige_from_trophies(trophies: int) -> int:
    return max(trophies, 0) // PRESTIGE_TROPHY_STEP


def trophies_required_for_prestige(prestige_level: int) -> int:
    return prestige_level * PRESTIGE_TROPHY_STEP


def calculate_prestige_price(
    current_trophies: int,
    desired_prestige: int,
    is_duo_carry: bool = False,
) -> PriceBreakdown | None:
    trophies_needed = trophies_required_for_prestige(desired_prestige) - current_trophies
    if trophies_needed <= 0:
        return None

    base_price = trophies_needed * PRICE_PER_PRESTIGE_TROPHY
    multiplier = PRESTIGE_DUO_MULTIPLIER if is_duo_carry else 1.0
    notes = [f"{trophies_needed:,} trophies needed, calculated from the brawler's live trophy count."]

    if is_duo_carry:
        notes.append(f"Duo carry multiplier applied ({PRESTIGE_DUO_MULTIPLIER}x) — you keep your account.")

    raw_price = base_price * multiplier
    final_price = max(raw_price, MINIMUM_ORDER_PRICE)
    if final_price > raw_price:
        notes.append("Minimum order price applied.")

    return PriceBreakdown(
        base_price=base_price,
        discount_rate=0.0,
        multiplier=multiplier,
        final_price=round(final_price, 2),
        notes=notes,
    )


def get_other_option(key: str) -> dict | None:
    for option in OTHER_SERVICE_OPTIONS:
        if option["key"] == key:
            return option
    return None


def calculate_other_price(option_key: str, detail_text: str) -> PriceBreakdown | None:
    option = get_other_option(option_key)
    if option is None:
        return None

    base_price = option.get("base_price")
    notes = [option["pricing_note"]]

    if base_price is None:
        return PriceBreakdown(base_price=0.0, discount_rate=0.0, multiplier=1.0, final_price=0.0, notes=notes)

    per_unit_price = option.get("per_unit_price")
    if per_unit_price:
        digits = re.findall(r"\d+", detail_text or "")
        quantity = int(digits[0]) if digits else 0
        scaled_price = max(base_price, quantity * per_unit_price)
        return PriceBreakdown(base_price=base_price, discount_rate=0.0, multiplier=1.0, final_price=round(scaled_price, 2), notes=notes)

    return PriceBreakdown(base_price=base_price, discount_rate=0.0, multiplier=1.0, final_price=round(base_price, 2), notes=notes)
