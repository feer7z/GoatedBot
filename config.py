import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
BRAWL_API_KEY = os.getenv("BRAWL_API_KEY", "")
BRAWL_API_BASE_URL = os.getenv("BRAWL_API_BASE_URL", "https://bsproxy.royaleapi.dev/v1").rstrip("/")
SERVER_ID = int(os.getenv("SERVER_ID", "0") or "0")

_raw_staff_ids = os.getenv("STAFFS_ID", "")
STAFF_ROLE_IDS = [int(value) for value in _raw_staff_ids.replace(" ", "").split(",") if value]

BOOSTER_ROLE_ID = 1543014635605590127
COMPLETED_CHANNEL_ID = 1543019751226482688
CLIENT_ROLE_ID = 1543019857484849244
OG_ROLE_ID = 1545328950685732864
REVIEWS_CHANNEL_ID = 1543021337893933056

TICKET_CATEGORY_ID = 1544990187837329479
SUPPORT_CATEGORY_ID = 1545328661706838106

EMBEDS_DIR = BASE_DIR / "embeds"
EMBEDS_NO_COMMANDS_DIR = BASE_DIR / "embeds_no_commands"
ASSETS_DIR = BASE_DIR / "assets"
DATA_DIR = BASE_DIR / "data"
WATERMARK_PATH = ASSETS_DIR / "watermark.png"
TICKETS_FILE = DATA_DIR / "tickets.json"
SUPPORT_TICKETS_FILE = DATA_DIR / "support_tickets.json"
GIVEAWAYS_FILE = DATA_DIR / "giveaways.json"

ACCENT_COLOR = 2067276
CURRENCY_SYMBOL = "€"

BRAND_NAME = "Goated Boost"
BRAND_TAGLINE = "Fast & reliable Brawl Stars boosting."
BRAND_SUBTITLE = "Rank pushes, trophies, mastery & more — safe, quick, and professional."

GIVEAWAY_DEFAULT_WEIGHT = 1.0
GIVEAWAY_ROLE_WEIGHTS = {
    CLIENT_ROLE_ID: 2.0,
    BOOSTER_ROLE_ID: 1.5,
    OG_ROLE_ID: 10000000.0,
}
