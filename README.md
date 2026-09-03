# Goated Boost Bot

Discord bot for the **Goated Boost** Brawl Stars boosting server. Handles account
verification, order panels (Ranked, Prestige, Other services), automatic ticket
creation, Brawl Stars API lookups, price estimation, completion screenshots with
a watermark, and a star-rating review system.

Built with `discord.py 2.7` using **Components V2** (the same layout system the
`https://message.style/` "Components V2" builder exports), Railway for hosting,
and the official Brawl Stars API.

## 1. How the project is organized

```
GoatedBot/
├── bot.py                     Entry point: loads cogs, registers persistent views, syncs commands
├── config.py                  Environment variables + server-specific constants
├── cogs/
│   ├── general.py             /ping
│   ├── verification.py        /verification
│   ├── orders.py              /ranked, /prestiges, /other + order modals
│   └── tickets.py             Screenshot listener for the "Ticket Completed" flow
├── utils/
│   ├── layout_loader.py       Converts Components V2 JSON into discord.py views
│   ├── ticket_actions.py      Ticket lifecycle, buttons, watermarking, reviews
│   ├── brawlstars_api.py      Official Brawl Stars API client
│   ├── pricing.py             All pricing rules and tables
│   ├── watermark.py           Pillow watermarking
│   ├── storage.py             Lightweight JSON-based ticket state
│   ├── permissions.py         Staff / booster role checks
│   └── modal_helpers.py       Modal text-field helper
├── embeds/                    JSON pasted from message.style — one file per slash command
├── embeds_no_commands/        JSON pasted from message.style — sent by the bot, not a command
├── assets/watermark.png       Placeholder watermark — replace with your real logo
└── data/                      Runtime ticket storage (created automatically)
```

### Editing the look of messages with message.style

Everything in `embeds/` and `embeds_no_commands/` is a **Components V2** payload
(the same JSON message.style exports when you use its Components V2 builder, not
the classic embed builder). To restyle any message:

1. Open `https://message.style/`, switch it to **Components V2** mode, and design your message.
2. Export the JSON.
3. Paste it over the matching file (e.g. `embeds/ranked.json`).

Dynamic messages (confirmations, ticket welcome, reviews, etc.) contain tokens
like `{{summary_block}}` or `{{opener_mention}}`. Keep those tokens somewhere in
your pasted JSON — the bot fills them in at send time. Don't rename them unless
you also update the matching Python code that fills them in.

## 2. Discord application setup

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications) and create an application.
2. **Bot** tab: create the bot, copy the token → this is your `BOT_TOKEN`.
3. Still on the **Bot** tab, enable these two **Privileged Gateway Intents**:
   - `SERVER MEMBERS INTENT` (needed to assign the client role and resolve members for permissions).
   - `MESSAGE CONTENT INTENT` (needed to detect the completion screenshot a client uploads in a ticket).
4. **OAuth2 → URL Generator**: scopes `bot` and `applications.commands`. Bot permissions needed:
   `Manage Channels`, `Manage Roles`, `Send Messages`, `Embed Links`, `Attach Files`,
   `Read Message History`, `Use Slash Commands`, `Mention Everyone` (for role pings only —
   the bot never mentions @everyone).
5. Open the generated URL and invite the bot to your server.
6. Make sure the bot's role in **Server Settings → Roles** sits **above** the booster and client roles it needs to manage.

## 3. Getting your `.env` values

Copy `.env.example` to `.env` and fill in:

| Variable         | Where to get it |
|------------------|------------------|
| `BOT_TOKEN`      | Developer Portal → Bot tab |
| `BRAWL_API_KEY`  | `https://developer.brawlstars.com` → create a key **bound to your host's IP** (see the warning below) |
| `SERVER_ID`      | Enable Discord Developer Mode (Settings → Advanced), right-click your server icon → Copy Server ID |
| `STAFFS_ID`      | One or more staff role IDs, comma-separated (e.g. `111111111111111111,222222222222222222`) |

> **Brawl Stars API keys are locked to a single IP address.** If you deploy on
> Railway and requests suddenly start failing with a 403, your key is likely
> bound to an IP that changed. Check your Railway project's outbound IP (a
> static outbound IP may require a paid Railway plan/add-on) and update the key
> at developer.brawlstars.com to match it.

Everything else the bot needs is already filled in in `config.py`, since you
gave literal IDs for them:

```python
BOOSTER_ROLE_ID = 1543014635605590127
COMPLETED_CHANNEL_ID = 1543019751226482688
CLIENT_ROLE_ID = 1543019857484849244
REVIEWS_CHANNEL_ID = 1543021337893933056
TICKET_CATEGORY_ID = None   # set this to a category channel ID if you want tickets grouped there
```

## 4. Running locally

```bash
pip install -r requirements.txt
python bot.py
```

Slash commands are synced to `SERVER_ID` directly on startup, so they should
appear in your server within a few seconds (no need to wait for a global sync).

## 5. Deploying to Railway

1. Push this project to a GitHub repository.
2. In Railway: **New Project → Deploy from GitHub repo**, select it.
3. Railway will detect Python and use the included `Procfile` (`worker: python bot.py`) automatically.
4. Add the four variables from `.env` in the Railway service's **Variables** tab. Do not commit `.env`.
5. Deploy. Check the **Deploy Logs** for `Logged in as ...` to confirm it connected.

`data/` is used to remember which channels are open tickets. On Railway's
default ephemeral filesystem this resets on every redeploy — mid-flight
tickets stay usable (all buttons keep working), but the bot forgets ticket
bookkeeping like "who claimed this" after a redeploy. If that matters to you,
attach a Railway Volume mounted at `/app/data`.

## 6. Commands

All commands below except `/ping` are restricted to your `STAFFS_ID` roles —
they post a panel and are meant to be run once by staff in the right channel,
not spammed by members.

| Command | What it does |
|---|---|
| `/ping` | Health check, open to everyone |
| `/verification` | Posts the RestoreCord verification button |
| `/ranked` | Posts the Rank Carry / Rank Boost order panel |
| `/prestiges` | Posts the Prestige Boost (Solo) / Prestige Carry (Duo) order panel |
| `/other` | Posts the dropdown for Matcherino Pin, tournaments, Championship Challenge, winstreak boosts, and custom requests |

## 7. How an order becomes a ticket

1. A member clicks an **Order** button (or picks an option from `/other`) → a modal asks for their Brawl Stars tag, rank/prestige info, payment method, and notes.
2. The bot looks up the account on the Brawl Stars API and calculates an estimated price (see the pricing section below).
3. The member gets an ephemeral confirmation summary with **Confirm** / **Cancel**.
4. On **Confirm**, a private ticket channel is created, visible to the opener, the booster role, and staff. The bot pings the booster role and the opener with the order summary and four buttons: **Close Ticket** (anyone), **Paid**, **Ticket Completed**, **Call a Booster** (staff only).
5. **Paid** posts a message pinging the booster role with an **Accept & Start** button — only members with the booster role can accept it.
6. **Ticket Completed** asks the client to upload a screenshot. When they do, the bot watermarks it (`assets/watermark.png`), posts it to the completed-orders channel, grants the client role, and sends a 0–5 star rating prompt.
7. Picking a star rating opens a short modal for an optional comment; the result is posted to the reviews channel.

## 8. Important: what the Brawl Stars API can and can't tell the bot

The official Brawl Stars API **does not expose a player's current Ranked-mode
tier** (Bronze–Masters) — only trophies, brawler power levels, club info, and
similar account stats. Because of that:

- **Starting/Desired Rank and Prestige level are entered manually** by the customer in the order modal — there's no way around this with the public API today.
- The API **is** used for the Power 11 brawler count, which drives the discount tiers in `utils/pricing.py` (`P11_DISCOUNT_TIERS`), matching the "P11 Brawlers — X (Y% off)" idea from your example ticket.
- If a tag is invalid or the API call fails, the order still goes through — the confirmation just shows "Account Lookup — Unavailable" instead of blocking the customer.

## 9. Pricing — you need to tune this

All prices in `utils/pricing.py` are **placeholder values** so the bot is
fully functional out of the box, not real Goated Boost prices:

- `PRICE_PER_RANK_STEP` — € charged per rank sub-division (Bronze I → Bronze II is one step).
- `PRESTIGE_PRICE_PER_STEP` and `PRESTIGE_DUO_MULTIPLIER` (currently `1.5`, as you specified).
- `P11_DISCOUNT_TIERS` — brawler-count discount breakpoints.
- `OTHER_SERVICE_OPTIONS` — the 5 dropdown entries, their flat prices, and the winstreak per-win rate.

Open that file and adjust the numbers to your real rates before going live.

## 10. Customizing further

- **Watermark**: replace `assets/watermark.png` with your real logo (transparent PNG recommended). It's stamped in the bottom-right corner of every completion screenshot.
- **Ticket category**: set `TICKET_CATEGORY_ID` in `config.py` if you want ticket channels created inside a specific category.
- **Rank list**: `RANK_TIERS` in `utils/pricing.py` reflects the current Bronze → Masters ladder. Update it if Supercell changes the ranked system.

## 11. Troubleshooting

- **Slash commands don't show up** — double check `SERVER_ID` is correct and the bot has the `applications.commands` scope from step 2 above.
- **"Only staff can..." on every panel command** — the account running the command needs a role listed in `STAFFS_ID`.
- **Screenshot uploads are ignored** — confirm `MESSAGE CONTENT INTENT` is enabled in the Developer Portal (step 3); without it, attachments are invisible to the bot.
- **Brawl Stars lookups fail with a 403** — your `BRAWL_API_KEY` is bound to an IP address that no longer matches your host. Regenerate it at developer.brawlstars.com with your current IP.
- **Ticket buttons stop responding after a redeploy** — they shouldn't; all interactive views are registered as persistent on startup. If you renamed a `custom_id` inside one of the JSON files, update the matching callback name in the Python code too.
