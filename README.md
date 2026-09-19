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
│   ├── tickets.py             Screenshot listener for the "Ticket Completed" flow
│   ├── support.py             /support panel command
│   ├── giveaways.py           /giveaway command, entry button, auto-end loop
│   └── welcome.py             on_member_join DM + /offers
├── utils/
│   ├── layout_loader.py       Converts Components V2 JSON into discord.py views
│   ├── ticket_actions.py      Order-ticket lifecycle, buttons, watermarking, reviews
│   ├── support_actions.py     Support-ticket lifecycle (ticket-tool style), DM survey
│   ├── giveaways.py           Giveaway storage, duration parsing, weighted winner draw
│   ├── welcome_offers.py      Personalized starter-offer calculation and DM-to-ticket flow
│   ├── brawlstars_api.py      Official Brawl Stars API client
│   ├── pricing.py             All pricing rules and tables
│   ├── watermark.py           Pillow watermarking
│   ├── storage.py             Lightweight JSON-based order-ticket state
│   ├── permissions.py         Staff / booster role checks
│   ├── modal_helpers.py       Modal text-field helper
│   └── text_utils.py          Shared channel-name and notice-view helpers
├── embeds/                    JSON pasted from message.style — one file per slash command
├── embeds_no_commands/        JSON pasted from message.style — sent by the bot, not a command
├── assets/watermark.png       Placeholder watermark — replace with your real logo
└── data/                      Runtime ticket/giveaway storage (created automatically)
```

### Editing the look of messages with message.style

Everything in `embeds/` and `embeds_no_commands/` is a **Components V2** payload
(the same JSON message.style exports when you use its Components V2 builder, not
the classic embed builder). To restyle any message:

1. Open `https://message.style/`, switch it to **Components V2** mode, and design your message.
2. Export the JSON.
3. Paste it over the matching file (e.g. `embeds/ranked.json`).

Dynamic messages (ticket welcome, reviews, giveaways, etc.) contain tokens
like `{{summary_block}}` or `{{opener_mention}}`. Keep those tokens somewhere in
your pasted JSON — the bot fills them in at send time. Don't rename them unless
you also update the matching Python code that fills them in. The brand accent
color used across every message is `config.ACCENT_COLOR` (currently `#1f8b4c`).

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

| Variable              | Where to get it |
|-----------------------|------------------|
| `BOT_TOKEN`           | Developer Portal → Bot tab |
| `BRAWL_API_KEY`       | `https://developer.brawlstars.com` → create a key (see below for which IP to whitelist) |
| `BRAWL_API_BASE_URL`  | Leave as the default unless you want to call the official API directly (see below) |
| `SERVER_ID`           | Enable Discord Developer Mode (Settings → Advanced), right-click your server icon → Copy Server ID |
| `STAFFS_ID`           | One or more staff role IDs, comma-separated (e.g. `111111111111111111,222222222222222222`) |

### Brawl Stars API access: proxy vs. direct

Brawl Stars API keys are locked to a single IP address, and Railway's default
plan doesn't give you a static outbound IP — so a key created for your laptop
will fail once the bot runs on Railway. This project defaults
`BRAWL_API_BASE_URL` to **RoyaleAPI's proxy** (`https://bsproxy.royaleapi.dev/v1`),
a community-run relay that sits in front of the official API with its own
already-whitelisted IP, so your key keeps working no matter where the bot is
hosted or how often the host's IP changes.

To make this work:

1. Create your key at `https://developer.brawlstars.com` (not
   `developer.clashofclans.com` — that's a different game; RoyaleAPI's own docs
   page links there by mistake, which is likely where that link came from).
2. When asked for an allowed IP address, whitelist **`45.79.218.79`**
   (RoyaleAPI's proxy IP — not your own). This is the current IP as of
   RoyaleAPI's Feb 2022 update; if it ever stops working, check
   `https://docs.royaleapi.com/proxy.html` for a new one.
3. Leave `BRAWL_API_BASE_URL` as the default in `.env.example`.

If you'd rather call `api.brawlstars.com` directly (e.g. you have a static IP),
set `BRAWL_API_BASE_URL=https://api.brawlstars.com/v1` and whitelist your own
server's IP on the key instead. Since RoyaleAPI's proxy is a third-party
service, it can occasionally have its own downtime independent of Supercell's
API — direct access avoids that dependency if a static IP is available to you.

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

Panel-posting and giveaway commands are restricted to your `STAFFS_ID` roles.
Ticket-management commands (`/close`, `/paid`, `/completed`, `/callbooster`)
use the same checks as their matching buttons — `/close` works for anyone in
the ticket, the rest need staff. `/ping` and `/offers` are open to everyone.

| Command | What it does |
|---|---|
| `/ping` | Reports gateway and response latency in ms |
| `/verification` | Posts the RestoreCord verification button |
| `/ranked` | Posts the Rank Carry / Rank Boost order panel |
| `/prestiges` | Posts the Prestige Boost (Solo) / Prestige Carry (Duo) order panel |
| `/other` | Posts the dropdown for Matcherino Pin, tournaments, Championship Challenge, winstreak boosts, and custom requests |
| `/support` | Posts the support ticket panel (Ticket Tool style) |
| `/giveaway prize duration winners [required_role]` | Starts a giveaway that auto-ends and announces winners |
| `/offers` | Resends the personalized starter-offers DM to whoever runs it |
| `/offer member` | Staff — sends the offers DM to one specific member |
| `/offerall` | Staff — sends the offers DM to every member, one at a time with a short delay between each to respect Discord's rate limits |
| `/close` | Same as the Close Ticket button |
| `/paid` | Same as the Paid button |
| `/completed` | Same as the Ticket Completed button |
| `/callbooster` | Same as the Call a Booster button |

Panel commands (`/ranked`, `/prestiges`, `/other`, `/verification`, `/support`)
reply to the staff member privately and post the actual panel as a normal bot
message — so the panel never shows Discord's "*Name* used `/command`" header
above it.

## 7. How an order becomes a ticket

The panels are deliberately **one click to buy** — nothing is asked before the
ticket exists, so a customer is never staring at a form before they've even
talked to anyone:

1. A member clicks an **Order** button (or picks an option from `/other`) → a private ticket channel is created immediately, no questions asked. It's visible to the opener, the booster role, and staff.
2. Inside the ticket, the bot pings the booster role and the opener and shows the chosen service plus a green **Fill Order Details** button, along with **Close Ticket** and **Call a Booster**.
3. Clicking **Fill Order Details** opens the form for that specific service (the bot remembers which product the ticket was opened for, so the right form appears automatically). Only the ticket opener or staff can use it.
4. On submit, the bot looks up the account on the Brawl Stars API, calculates the price, and **edits the original ticket message in place** — the pending message becomes the full order summary with **Paid**, **Ticket Completed**, and the rest of the staff buttons. If a form entry is wrong (bad tag, unknown brawler, etc.), the bot explains the problem privately and the button stays available to try again.
5. **Paid** posts a message pinging the booster role with an **Accept & Start** button — only members with the booster role can accept it. Whoever accepts is remembered as the booster credited on the final showcase post.
6. **Ticket Completed** asks the client to upload a screenshot. Once uploaded, the bot watermarks it (`assets/watermark.png`) and asks the client one more thing: **Show My Name** or **Stay Anonymous** in the showcase post.
7. After that choice, the bot posts the watermarked screenshot to the completed-orders channel with price, payment method, booster, and — for Prestige orders — the brawler name, starting trophies (from order time) and current trophies (re-fetched live from the API at completion time). It also grants the client role and sends a 0–5 star rating prompt in the ticket.
8. Picking a star rating opens a short modal for an optional comment; the result is posted to the reviews channel.

Tickets opened from the **welcome offers DM** (section 13) skip steps 2–4
entirely — the offer already knows the tag, price, and service, so those
tickets arrive fully filled in from the start.

**Surviving a redeploy.** If `data/tickets.json` gets wiped by a Railway
redeploy (see section 5), `/paid` and `/completed` — and their matching
buttons — automatically rebuild a minimal record for any channel named
`ticket-...` by reading who has channel access (skipping staff and boosters
to find the actual client), so a ticket opened before the redeploy stays
manageable. The one thing that doesn't come back is the original order
details (price, brawler, etc.) — the recovered ticket just shows "Boost" as a
placeholder, so double check pricing manually for tickets opened before the
wipe.

Both the **completed-orders post** and every **review result** end with a
**Get Your Offer Now** button that opens the same tag modal as the welcome DM
— a passive sales funnel for anyone browsing those channels.

## 8. Prestige orders: brawler-based, exact pricing

Prestige orders no longer ask the customer to type their starting Prestige.
Instead, the modal asks for their **player tag** and the **brawler's name**,
and the bot does the rest:

1. It fetches the account from the Brawl Stars API and finds that specific brawler.
2. It reads the brawler's **live trophy count** — Prestige in Brawl Stars is per-brawler and unlocks at every 1,000 trophies (Prestige 1 at 1,000, Prestige 2 at 2,000, and so on, uncapped), so the current Prestige level is `trophies // 1000`.
3. The price is `(trophies needed to reach the desired Prestige) × PRICE_PER_PRESTIGE_TROPHY`, exact — not a rounded step or estimate. Duo carries multiply that by `PRESTIGE_DUO_MULTIPLIER`.
4. If the tag or brawler name can't be resolved, the order is blocked with an error instead of falling back to a guess, since an exact price requires real data.

**The Power 11 brawler-count discount only applies to `/ranked` orders now**
(`P11_DISCOUNT_TIERS` in `utils/pricing.py`) — Prestige pricing no longer uses it.

## 9. What the Brawl Stars API exposes (and how the bot uses it)

Earlier versions of this README said the API couldn't expose a player's
Ranked tier or win streak — that turned out to be wrong (likely added to the
API after the docs Claude checked were last updated). Confirmed against real
API responses, the player endpoint includes:

- `rankedRank` (an integer position) and `rankedRankName` (e.g. `"MYTHIC I"`) — the account's **current-season** Ranked standing. `rankedRank` lines up exactly with `RANK_TIERS` in `utils/pricing.py` (Mythic I is position 13, Masters I is 19, etc.), so `get_current_ranked_tier()` uses the number directly and only falls back to parsing the name string if it's missing.
- Per-brawler `maxWinStreak` — each brawler's best-ever win streak, used for the Winstreak Boost offer.
- Per-brawler `prestigeLevel` — the account's already-computed Prestige level; the bot still derives it independently from `trophies` (see section 8) since that keeps pricing based on one source of truth, but the two should always agree.

Because of this:

- **`/ranked` auto-detects the starting rank** the same way `/prestiges` auto-detects starting trophies — the modal only asks for the *desired* rank. If an account hasn't played a Ranked match this season (`rankedRank`/`rankedRankName` absent), the order is blocked with a clear message asking them to play one first, rather than guessing.
- **Winstreak Boost** (in `/other` and in the welcome offers) auto-detects the account's best current streak from whichever brawler holds it, and prices reaching the next multiple of 100 — exactly the "beat your record, multiple of 100" idea from the original spec, just pointed at the right stat (`maxWinStreak`, not cumulative victories).
- The Power 11 brawler count is still used only for the `/ranked` discount tiers (`P11_DISCOUNT_TIERS`), unrelated to any of the above.
- If the account lookup itself fails (bad tag, API/proxy down), Ranked, Prestige, and Winstreak orders are all blocked with a clear error rather than falling back to a guess — consistent with the "exact price or nothing" approach used throughout.

## 10. Pricing — you need to tune this

All prices in `utils/pricing.py` are **placeholder values** so the bot is
fully functional out of the box, not real Goated Boost prices:

- `PRICE_PER_RANK_STEP` — € charged per rank sub-division (Bronze I → Bronze II is one step).
- `PRICE_PER_PRESTIGE_TROPHY` and `PRESTIGE_DUO_MULTIPLIER` (currently `1.5`, as you specified) — Prestige is priced per trophy needed, not per Prestige level, since a P1→P2 gap and a P4→P5 gap are both exactly 1,000 trophies anyway.
- `P11_DISCOUNT_TIERS` — brawler-count discount breakpoints, Ranked only.
- `OTHER_SERVICE_OPTIONS` — the 5 dropdown entries, their flat prices, and the winstreak per-win rate.
- `MINIMUM_ORDER_PRICE` — floor applied to every calculated price.

Open that file and adjust the numbers to your real rates before going live.

## 11. Support tickets (`/support`)

A separate, simpler ticket system for general support — not tied to an order
or a price, styled after Ticket Tool:

1. `/support` posts a panel with an **Open Ticket** button.
2. Clicking it asks the member what they need help with, then creates a private channel (opener + staff only — no booster role access, unlike order tickets).
3. Inside: **Claim** (staff only, marks who's handling it) and **Close Ticket** (the opener or staff).
4. On close, the bot DMs the opener a 0–5 star satisfaction survey (same style as the order review flow) before deleting the channel. If the member has DMs closed, the ticket still closes normally — the survey is just skipped.
5. Survey results post to the same reviews channel as order reviews, labeled "Support".

Support tickets use their own storage file (`data/support_tickets.json`) and,
optionally, their own category — set `SUPPORT_CATEGORY_ID` in `config.py`.

## 12. Giveaways (`/giveaway`)

`/giveaway prize:"Nitro" duration:1d winners:1` posts a giveaway with an
**Enter** button and ends itself automatically (checked every 30 seconds by a
background loop, so it survives restarts/redeploys — it re-reads
`data/giveaways.json` rather than relying on an in-memory timer).

**Entry requirement (visible).** The optional `required_role` parameter gates
who can even press Enter — pick a role in Discord's own role picker when
running the command (e.g. your "3 Invites" role) and only members who have it
can join. Discord shows a friendly error to anyone else. This is checked once,
at entry time. Leave it blank for an open-to-everyone giveaway. Since it's a
per-giveaway command option rather than a fixed config value, the same command
works for a "5 Invites" giveaway later without touching any code — and the
requirement is shown right in the giveaway message so people know to go earn it.

**Winner odds (hidden).** Separately, winners are picked with **weighted random
selection** among whoever entered: some roles can be given better odds via
`GIVEAWAY_ROLE_WEIGHTS` in `config.py`:

```python
GIVEAWAY_DEFAULT_WEIGHT = 1.0
GIVEAWAY_ROLE_WEIGHTS = {
    CLIENT_ROLE_ID: 2.0,
    BOOSTER_ROLE_ID: 1.5,
}
```

A member with a role worth `2.0` is twice as likely to win as someone with the
default weight — but nothing in any command, button, or message ever displays
these numbers or which roles have them; it's a config-only lever, exactly as
you asked. Edit the dict to add, remove, or reweight roles; it isn't exposed
through any command. This is intentionally separate from `required_role`: the
requirement decides *who can enter* and is meant to be seen, the weights only
influence *who wins among entrants* and are meant to stay invisible.

## 13. Welcome offers (join DM / `/offers`)

As soon as someone joins the server (and any time via `/offers`, in case the
join DM was missed or they just want to check again), the bot DMs them a
**Show Me Offers** button. Clicking it opens a modal for their Brawl Stars
player tag — required, since every offer below is calculated from their real
account data, not a guess:

- **🏆 Winstreak Boost** — finds whichever brawler holds the account's best `maxWinStreak` and offers to beat it up to the next multiple of 100 (e.g. a 142-win record → priced to reach 200), using the same rate as the `winstreak_boost` entry in `OTHER_SERVICE_OPTIONS`. Skipped entirely if no brawler has a win streak yet.
- **⭐ Prestige Push** — finds whichever of their brawlers has the *smallest*
  trophy gap left before Prestige 3 and prices it with the exact same
  `calculate_prestige_price` function `/prestiges` uses.
- **🎯 Ranked Push** — reads their current-season rank (`rankedRank`/`rankedRankName`) and prices pushing exactly one tier up, using the same `calculate_rank_price` function `/ranked` uses. If the account hasn't played Ranked this season yet, this becomes a plain "open a ticket and tell us your rank" card instead, since there's nothing to read.

Each card's **Order This** (or **Ask About Ranked**) button creates a ticket
directly — no extra confirmation step, since clicking it *is* the acceptance,
same as you described. These tickets skip the Payment Method line (nothing
asks for it in the DM, to keep the flow to a single tap) and, for the Ranked
card, skip a fixed price too — both get filled in by staff once the ticket is
open, exactly like a normal manual sale.

If a member has DMs from the server disabled, the join DM just silently fails
to send — there's no fallback channel post, so as not to publicly call out
who didn't get it.

## 14. Customizing further

- **Watermark**: replace `assets/watermark.png` with your real logo (transparent PNG recommended). It's stamped in the bottom-right corner of every completion screenshot.
- **Ticket category**: set `TICKET_CATEGORY_ID` (orders) or `SUPPORT_CATEGORY_ID` (support) in `config.py` if you want ticket channels created inside a specific category.
- **Rank list**: `RANK_TIERS` in `utils/pricing.py` reflects the current Bronze → Pro ladder (Bronze–Legendary have 3 tiers each, Masters has 3, Pro is a single top rank — 22 total). Update it if Supercell changes the ranked system.
- **Support survey destination**: both order reviews and support-ticket surveys currently post to `REVIEWS_CHANNEL_ID`. Point support feedback elsewhere by adding a second channel constant and passing it through `_send_satisfaction_survey` in `utils/support_actions.py` if you'd rather keep them separate.
- **Emojis**: every custom emoji the bot uses (ranks, Prestige levels, P11, payment method, etc.) lives in one place, `utils/emojis.py`. Each is a plain `<:name:id>` string constant — to change one, edit its ID there; nothing else needs to change. `rank_emoji()`, `prestige_emoji()`, and `service_emoji()` map names/numbers to the right constant automatically, and `field()` builds one `emoji **Label** — value` line, which is what every order summary, completed post, and review is built from.

## 15. Troubleshooting

- **Slash commands don't show up** — double check `SERVER_ID` is correct and the bot has the `applications.commands` scope from step 2 above.
- **"Only staff can..." on every panel command** — the account running the command needs a role listed in `STAFFS_ID`.
- **Screenshot uploads are ignored** — confirm `MESSAGE CONTENT INTENT` is enabled in the Developer Portal (step 3); without it, attachments are invisible to the bot.
- **Brawl Stars lookups fail with "The Brawl Stars API rejected this request (403)"** — the key isn't whitelisted for the IP actually making the request. Using the default proxy? Whitelist `45.79.218.79` on the key (not your server's IP). Using `api.brawlstars.com` directly? Whitelist your server's current IP instead.
- **Brawl Stars lookups fail with "Player not found"** — this is a 404, a different problem from the one above: the tag itself wasn't recognized. Check for typos, make sure it starts with `#`, and confirm you didn't submit the modal's placeholder text (`#ABC123XYZ`) instead of a real tag.
- **A Prestige order won't confirm at all** — this is intentional: since the price is now calculated exactly from live trophy data, the bot blocks the order (with an explanation) instead of guessing if the tag or brawler name can't be resolved.
- **Support ticket closed without a DM survey arriving** — the member likely has DMs from server members/bots disabled. The ticket still closes normally; there's no fallback delivery for the survey by design, so as not to spam a public channel with what's meant to be a private ask.
- **A giveaway didn't end on time** — it ends on the next 30-second check after its timer expires, not to the second. If it never ends, confirm the bot process is actually running (Railway logs) — the loop only runs while the bot is connected.
- **New members never get the offers DM** — this needs `SERVER MEMBERS INTENT` enabled (same as the client-role step) to fire `on_member_join` at all; separately, some members simply have server DMs off, which the bot can't do anything about. `/offers` gives them (or you, for a quick test) a manual way to trigger the same DM.
- **A ticket is stuck showing "Fill Order Details"** — that just means nobody submitted the form yet; the order summary, **Paid** and **Ticket Completed** buttons only appear once it's filled in. Staff can click it on the customer's behalf if needed.
- **Ticket buttons stop responding after a redeploy** — they shouldn't; all interactive views are registered as persistent on startup. If you renamed a `custom_id` inside one of the JSON files, update the matching callback name in the Python code too.
