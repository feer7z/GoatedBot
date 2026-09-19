from __future__ import annotations

MATCHERINO_PIN = "<:matcherino_pin:1544950090572111882>"
WINSTREAK = "<:winstreak:1544950478872379452>"
P11 = "<:p11:1550627971201507458>"
MATCHERINO_TOURNAMENT = "<:matcherino_tournament:1544948966351704175>"

BRONZE = "<:bronze:1550628824255954964>"
SILVER = "<:silver:1550628849874632714>"
GOLD = "<:gold:1550628770157826168>"
DIAMOND = "<:diamond:1550628795298488370>"
MYTHIC = "<:mythic:1550628717557194882>"
LEGENDARY = "<:legendary:1550628747626020946>"
MASTERS = "<:masters:1550628648481194054>"
PRO = "<:pro:1550628682341556375>"

PRESTIGE_1 = "<:prestige_1:1550628478783717386>"
PRESTIGE_2 = "<:prestige_2:1550628410085347498>"
PRESTIGE_3 = "<:prestige_3:1550628360529379399>"

QUESTION = "<:question:1550628275456577587>"
INFO = "<:info:1545319940993589331>"
PAPER = "<:paper:1545332005753847828>"
GOATED = "<:goated:1545103884379230238>"
PAYMENT_METHOD = "<:payment_method:1550630677270241280>"

_RANK_BRACKET_EMOJIS = {
    "bronze": BRONZE,
    "silver": SILVER,
    "gold": GOLD,
    "diamond": DIAMOND,
    "mythic": MYTHIC,
    "legendary": LEGENDARY,
    "masters": MASTERS,
    "pro": PRO,
}

_PRESTIGE_EMOJIS = {
    1: PRESTIGE_1,
    2: PRESTIGE_2,
    3: PRESTIGE_3,
}

_SERVICE_EMOJIS = {
    "matcherino_pin": MATCHERINO_PIN,
    "matcherino_tournament": MATCHERINO_TOURNAMENT,
    "winstreak_boost": WINSTREAK,
    "championship_challenge": GOATED,
    "other_request": QUESTION,
}


def rank_emoji(rank_name: str) -> str:
    bracket = rank_name.strip().split(" ")[0].lower()
    return _RANK_BRACKET_EMOJIS.get(bracket, "")


def prestige_emoji(prestige_level: int) -> str:
    if prestige_level in _PRESTIGE_EMOJIS:
        return _PRESTIGE_EMOJIS[prestige_level]
    return _PRESTIGE_EMOJIS[max(_PRESTIGE_EMOJIS)]


def service_emoji(option_key: str) -> str:
    return _SERVICE_EMOJIS.get(option_key, GOATED)


def with_rank(rank_name: str) -> str:
    emoji = rank_emoji(rank_name)
    return f"{emoji} {rank_name}" if emoji else rank_name


def with_prestige(prestige_level: int) -> str:
    return f"{prestige_emoji(prestige_level)} Prestige {prestige_level}"


def field(emoji: str, label: str, value: str) -> str:
    return f"{emoji} **{label}** — {value}"
