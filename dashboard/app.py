from flask import (
    Flask, render_template, request, redirect, jsonify,
    session, abort, url_for, flash
)

import json
import os
import requests
import secrets
from functools import wraps
from urllib.parse import urlencode
from dotenv import load_dotenv


load_dotenv()


BOT_API_URL = os.getenv("BOT_API_URL", "http://127.0.0.1:10000").rstrip("/")

DASHBOARD_API_KEY = os.getenv(
    "DASHBOARD_API_KEY",
    ""
)


DISCORD_API_URL = "https://discord.com/api/v10"
DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID", "")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET", "")
DISCORD_REDIRECT_URI = os.getenv(
    "DISCORD_REDIRECT_URI",
    "http://127.0.0.1:5050/callback"
)
BOT_OWNER_ID = os.getenv("BOT_OWNER_ID", "")
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "")

# Discord permission bits.
ADMINISTRATOR_PERMISSION = 1 << 3
MANAGE_GUILD_PERMISSION = 1 << 5


def _bot_api_request(method, endpoint, payload=None, timeout=18):
    """Send an authenticated request from the dashboard to the bot service."""
    if not BOT_API_URL:
        return {"ok": False, "error": "BOT_API_URL is not configured"}

    if not DASHBOARD_API_KEY:
        return {"ok": False, "error": "DASHBOARD_API_KEY is not configured"}

    try:
        response = requests.request(
            method=method,
            url=f"{BOT_API_URL}{endpoint}",
            headers={"X-Dashboard-Key": DASHBOARD_API_KEY},
            json=payload,
            timeout=timeout,
        )
    except requests.RequestException as error:
        print(f"Bot API connection error ({endpoint}): {error}")
        return {"ok": False, "error": str(error)}

    try:
        result = response.json()
    except ValueError:
        result = {
            "ok": False,
            "error": response.text.strip() or "The bot returned an invalid response",
        }

    if not response.ok:
        result.setdefault("ok", False)
        result.setdefault("error", f"Bot API returned HTTP {response.status_code}")
        print(f"Bot API error ({endpoint}): {result.get('error')}")
        return result

    if isinstance(result, dict):
        result.setdefault("ok", True)
    return result


def bot_api_get(endpoint):
    result = _bot_api_request("GET", endpoint, timeout=5)
    if isinstance(result, dict) and result.get("ok") is False:
        return None
    return result


def bot_api_post(endpoint, payload=None):
    return _bot_api_request("POST", endpoint, payload=payload, timeout=18)


def save_and_apply_feature(feature, settings):
    """Send settings to the bot first, then ask the bot to apply them."""
    save_result = bot_api_post(
        f"/api/dashboard/settings/{feature}",
        settings,
    )
    if not isinstance(save_result, dict) or not save_result.get("ok"):
        return save_result or {
            "ok": False,
            "error": f"The bot could not save {feature} settings",
        }

    apply_result = bot_api_post(f"/api/dashboard/apply/{feature}")
    if not isinstance(apply_result, dict):
        return {
            "ok": False,
            "error": f"The bot returned an invalid response while applying {feature}",
        }
    return apply_result


def apply_to_discord(feature):
    return bot_api_post(f"/api/dashboard/apply/{feature}")


BASE_FOLDER = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_FOLDER, "templates"),
    static_folder=os.path.join(BASE_FOLDER, "static")
)

if not FLASK_SECRET_KEY:
    raise RuntimeError(
        "FLASK_SECRET_KEY is missing. Add it to the dashboard .env file."
    )

app.secret_key = FLASK_SECRET_KEY
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("FLASK_COOKIE_SECURE", "false").lower() == "true",
)


@app.after_request
def inject_discord_selector_script(response):
    """Load the shared Discord selector script on dashboard HTML pages."""
    content_type = response.headers.get("Content-Type", "")
    if "text/html" not in content_type:
        return response

    try:
        html = response.get_data(as_text=True)
        script = '<script src="/static/js/discord-selectors.js"></script>'
        if script not in html and "</body>" in html:
            html = html.replace("</body>", f"{script}</body>")
            response.set_data(html)
            response.headers["Content-Length"] = len(response.get_data())
    except (UnicodeDecodeError, RuntimeError):
        pass

    return response


def api_json(endpoint, default=None):
    """Fetch JSON from the running Discord bot API."""
    data = bot_api_get(endpoint)
    if data is None:
        return default if default is not None else []
    return data



def discord_user_avatar(user):
    avatar = user.get("avatar")
    user_id = user.get("id")

    if avatar and user_id:
        return (
            f"https://cdn.discordapp.com/avatars/"
            f"{user_id}/{avatar}.png?size=128"
        )

    return "https://cdn.discordapp.com/embed/avatars/0.png"


def guild_icon_url(guild):
    guild_id = guild.get("id")
    icon = guild.get("icon")

    if guild_id and icon:
        return (
            f"https://cdn.discordapp.com/icons/"
            f"{guild_id}/{icon}.png?size=128"
        )

    return ""


def guild_is_manageable(guild):
    if guild.get("owner"):
        return True

    try:
        permissions = int(guild.get("permissions", "0"))
    except (TypeError, ValueError):
        return False

    return bool(
        permissions & ADMINISTRATOR_PERMISSION
        or permissions & MANAGE_GUILD_PERMISSION
    )


def current_user():
    return session.get("discord_user")


def manageable_guilds():
    return session.get("manageable_guilds", [])


def is_bot_owner():
    user = current_user()

    return bool(
        user
        and BOT_OWNER_ID
        and str(user.get("id")) == str(BOT_OWNER_ID)
    )


def can_manage_guild(guild_id):
    return any(
        str(guild.get("id")) == str(guild_id)
        for guild in manageable_guilds()
    )


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            return redirect(url_for("login"))

        return view(*args, **kwargs)

    return wrapped


def owner_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            return redirect(url_for("login"))

        if not is_bot_owner():
            abort(403)

        return view(*args, **kwargs)

    return wrapped


@app.context_processor
def inject_auth_context():
    return {
        "current_user": current_user(),
        "selected_guild_id": session.get("selected_guild_id"),
        "is_bot_owner": is_bot_owner(),
        "discord_user_avatar": discord_user_avatar,
        "guild_icon_url": guild_icon_url,
    }


@app.before_request
def protect_dashboard():
    endpoint = request.endpoint or ""

    public_endpoints = {
        "login",
        "callback",
        "logout",
        "static",
        "invite_bot",
    }

    if endpoint in public_endpoints:
        return None

    if not current_user():
        return redirect(
            url_for("login")
        )

    # Owner-only global dashboard settings.
    if (
        endpoint == "settings"
        and not is_bot_owner()
    ):
        abort(403)

    selected_required_endpoints = {
        "welcome",
        "tickets",
        "moderation",
        "embeds",
        "reaction_roles",
        "rules",
        "economy",
        "polls",
        "giveaways",
        "jobs",
        "command_settings",
        "sticky_messages",
        "auto_announcements",
        "reminders",
        "role_manager",
        "logs",
        "deadside_factions",
    }

    if endpoint in selected_required_endpoints:
        selected_guild_id = session.get(
            "selected_guild_id"
        )

        if not selected_guild_id:
            return redirect(
                url_for("servers")
            )

        if not can_manage_guild(
            selected_guild_id
        ):
            session.pop(
                "selected_guild_id",
                None
            )

            return redirect(
                url_for("servers")
            )

    # Protect every API request containing a guild ID.
    guild_id = (
        request.view_args.get("guild_id")
        if request.view_args
        else None
    )

    if (
        guild_id
        and not can_manage_guild(guild_id)
    ):
        abort(403)

    return None


@app.route("/login")
def login():
    if current_user():
        return redirect(url_for("servers"))

    if not DISCORD_CLIENT_ID or not DISCORD_CLIENT_SECRET:
        return (
            "Discord OAuth is not configured. Add DISCORD_CLIENT_ID and "
            "DISCORD_CLIENT_SECRET to .env.",
            500,
        )

    state = secrets.token_urlsafe(32)
    session["oauth_state"] = state

    query = urlencode({
        "client_id": DISCORD_CLIENT_ID,
        "redirect_uri": DISCORD_REDIRECT_URI,
        "response_type": "code",
        "scope": "identify guilds",
        "state": state,
        "prompt": "none",
    })

    return redirect(f"https://discord.com/oauth2/authorize?{query}")


@app.route("/callback")
def callback():
    returned_state = request.args.get("state", "")
    expected_state = session.pop("oauth_state", "")

    if not returned_state or not secrets.compare_digest(
        returned_state,
        expected_state
    ):
        abort(400, "Invalid OAuth state.")

    code_value = request.args.get("code")

    if not code_value:
        abort(400, "Discord did not return an authorization code.")

    token_response = requests.post(
        f"{DISCORD_API_URL}/oauth2/token",
        data={
            "client_id": DISCORD_CLIENT_ID,
            "client_secret": DISCORD_CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code_value,
            "redirect_uri": DISCORD_REDIRECT_URI,
        },
        headers={
            "Content-Type": "application/x-www-form-urlencoded"
        },
        timeout=10,
    )
    token_response.raise_for_status()
    access_token = token_response.json()["access_token"]

    auth_headers = {
        "Authorization": f"Bearer {access_token}"
    }

    user_response = requests.get(
        f"{DISCORD_API_URL}/users/@me",
        headers=auth_headers,
        timeout=10,
    )
    user_response.raise_for_status()

    guilds_response = requests.get(
        f"{DISCORD_API_URL}/users/@me/guilds",
        headers=auth_headers,
        params={"with_counts": "true"},
        timeout=10,
    )
    guilds_response.raise_for_status()

    user = user_response.json()
    guilds = [
        guild
        for guild in guilds_response.json()
        if guild_is_manageable(guild)
    ]

    # Do not store the OAuth access token in Flask's client-side session.
    session.clear()
    session["discord_user"] = {
        "id": str(user.get("id")),
        "username": user.get("username"),
        "global_name": user.get("global_name"),
        "avatar": user.get("avatar"),
    }
    session["manageable_guilds"] = guilds

    return redirect(url_for("servers"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/servers")
@login_required
def servers():
    bot_guilds = bot_api_get("/api/guilds") or []
    bot_guild_ids = {
        str(guild.get("id"))
        for guild in bot_guilds
    }

    guilds = []

    for guild in manageable_guilds():
        item = dict(guild)
        item["bot_installed"] = str(item.get("id")) in bot_guild_ids
        guilds.append(item)

    return render_template(
        "servers.html",
        guilds=guilds,
        user=current_user(),
    )
    
@app.route("/invite")
def invite_bot():
    client_id = str(
        DISCORD_CLIENT_ID
    ).strip()

    if not client_id.isdigit():
        return (
            "DISCORD_CLIENT_ID is missing or invalid.",
            500
        )

    return redirect(
        "https://discord.com/oauth2/authorize"
        f"?client_id={client_id}"
    )

    print(f"BOT INVITE URL: {invite_url}")

    return redirect(invite_url)
    
    
@app.route("/select-server/<guild_id>")
@login_required
def select_server(guild_id):
    if not can_manage_guild(guild_id):
        abort(403)

    session["selected_guild_id"] = str(guild_id)
    return redirect(url_for("home"))


@app.route("/owner")
@owner_required
def owner_panel():
    status = bot_api_get("/api/bot-status") or {}
    commands_data = bot_api_get("/api/commands") or {}

    return render_template(
        "owner.html",
        bot_status=status,
        commands_data=commands_data,
    )


@app.route("/api/guilds")
def dashboard_guilds():
    bot_guilds = api_json("/api/guilds", [])
    allowed_ids = {
        str(guild.get("id"))
        for guild in manageable_guilds()
    }

    return jsonify([
        guild
        for guild in bot_guilds
        if str(guild.get("id")) in allowed_ids
    ])


@app.route("/api/guild/<guild_id>/channels")
def dashboard_channels(guild_id):
    return jsonify(api_json(f"/api/guild/{guild_id}/channels", []))


@app.route("/api/guild/<guild_id>/roles")
def dashboard_roles(guild_id):
    return jsonify(api_json(f"/api/guild/{guild_id}/roles", []))

@app.route("/api/guild/<guild_id>/members")
def dashboard_members(guild_id):
    if not can_manage_guild(guild_id):
        abort(403)

    members = bot_api_get(
        f"/api/guild/{guild_id}/members"
    )

    if members is None:
        return jsonify({
            "error": "Could not load server members."
        }), 502

    return jsonify(members)


@app.route(
    "/api/guild/<guild_id>/member-role",
    methods=["POST"]
)
def dashboard_member_role(guild_id):
    if not can_manage_guild(guild_id):
        abort(403)

    payload = request.get_json(
        silent=True
    ) or {}

    try:
        response = requests.post(
            (
                f"{BOT_API_URL}/api/guild/"
                f"{guild_id}/member-role"
            ),
            headers={
                "X-Dashboard-Key": DASHBOARD_API_KEY
            },
            json={
                "member_id": payload.get("member_id"),
                "role_id": payload.get("role_id"),
                "action": payload.get("action")
            },
            timeout=18
        )

        result = response.json()

    except requests.RequestException as error:
        return jsonify({
            "error": str(error)
        }), 502

    except ValueError:
        return jsonify({
            "error": "The bot returned an invalid response."
        }), 502

    return jsonify(result), response.status_code

@app.route("/api/guild/<guild_id>/categories")
def dashboard_categories(guild_id):
    return jsonify(api_json(f"/api/guild/{guild_id}/categories", []))


@app.route("/api/guild/<guild_id>/all")
def dashboard_guild_all(guild_id):
    """Return channels, roles and categories in one request."""
    return jsonify({
        "channels": api_json(f"/api/guild/{guild_id}/channels", []),
        "roles": api_json(f"/api/guild/{guild_id}/roles", []),
        "categories": api_json(f"/api/guild/{guild_id}/categories", [])
    })



BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

ECONOMY_FILE = os.path.join(BASE_DIR, "economy.json")
WELCOME_FILE = os.path.join(BASE_DIR, "welcome.json")
TICKET_FILE = os.path.join(BASE_DIR, "ticket.json")
MODERATION_FILE = os.path.join(BASE_DIR, "moderation.json")
DASHBOARD_FILE = os.path.join(BASE_DIR, "dashboard.json")
EMBED_FILE = os.path.join(BASE_DIR, "embeds.json")
REACTION_ROLE_FILE = os.path.join(BASE_DIR, "reaction_roles.json")
RULES_FILE = os.path.join(BASE_DIR, "rules.json")
POLL_FILE = os.path.join(BASE_DIR, "polls.json")
GIVEAWAY_FILE = os.path.join(BASE_DIR, "giveaways.json")
COMMAND_PERMISSIONS_FILE = os.path.join(BASE_DIR, "command_permissions.json")
JOBS_CONFIG_FILE = os.path.join(BASE_DIR, "jobs_config.json")
STICKY_FILE = os.path.join(BASE_DIR, "sticky_messages.json")
ANNOUNCEMENTS_FILE = os.path.join(BASE_DIR,"auto_announcements.json")
REMINDERS_FILE = os.path.join(BASE_DIR,"reminders.json")
ROLE_MANAGER_FILE = os.path.join(BASE_DIR,"role_manager.json")
LOGS_FILE = os.path.join(BASE_DIR, "logs.json")
PERMISSIONS_FILE = os.path.join(BASE_DIR, "permission_manager.json")
DEADSIDE_FILE = os.path.join(BASE_DIR, "deadside.json")
DAYZ_FILE = os.path.join(BASE_DIR, "dayz.json")
TRANSCRIPTS_FOLDER = os.path.join(BASE_DIR, "ticket_transcripts")

def load_or_create_json(path, default):
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as file:
            json.dump(default, file, indent=4, ensure_ascii=False)
        return default.copy()

    try:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
            return data if isinstance(data, dict) else default.copy()
    except (OSError, json.JSONDecodeError):
        return default.copy()


@app.route("/")
def home():

    status = bot_api_get(
        "/api/bot-status"
    )

    commands_data = bot_api_get(
        "/api/commands"
    )

    if status is None:
        status = {
            "online": False,
            "bot_name": "Pirates Bot",
            "servers": 0,
            "members": 0,
            "latency_ms": 0
        }

    if commands_data is None:
        commands_data = {
            "prefix_commands": [],
            "slash_commands": [],
            "total": 0
        }

    return render_template(
        "index.html",
        bot_status=status,
        commands_data=commands_data
    )


@app.route("/commands")
def commands_page():

    commands_data = bot_api_get(
        "/api/commands"
    )

    if commands_data is None:
        commands_data = {
            "prefix_commands": [],
            "slash_commands": [],
            "total": 0
        }

    return render_template(
        "commands.html",
        commands_data=commands_data
    )
    
    
@app.route("/economy", methods=["GET", "POST"])
def economy():

    with open(ECONOMY_FILE, "r", encoding="utf-8") as file:
        economy = json.load(file)

    # ---------- Defaults ----------
    economy.setdefault("work", {
        "min_reward": 10,
        "max_reward": 100,
        "cooldown": 600
    })

    economy.setdefault("crime", {
        "success_chance": 50,
        "min_reward": 50,
        "max_reward": 250,
        "fail_loss": 50,
        "cooldown": 900
    })

    economy.setdefault("rob", {
        "success_chance": 40,
        "min_reward": 10,
        "max_reward": 100,
        "fail_loss": 50,
        "cooldown": 900
    })

    economy.setdefault("blackjack", {
        "min_bet": 10,
        "max_bet": 1000,
        "cooldown": 45
    })

    economy.setdefault("roulette", {
        "min_bet": 10,
        "max_bet": 1000,
        "cooldown": 60
    })

    economy.setdefault("daily", {
        "reward": 500,
        "cooldown": 86400
    })

    economy.setdefault("weekly", {
        "reward": 2500,
        "cooldown": 604800
    })

    economy.setdefault("bank", {
        "max_storage": 1000000,
        "interest_rate": 0,
        "interest_cooldown": 86400
    })

    if request.method == "POST":
        # Leave your existing save code here for now.
        with open(ECONOMY_FILE, "w", encoding="utf-8") as file:
            json.dump(economy, file, indent=4)

        apply_result = save_and_apply_feature("economy", economy)

    return render_template(
        "economy.html",
        economy=economy
    )
    
@app.route("/welcome", methods=["GET", "POST"])
def welcome():

    with open(WELCOME_FILE, "r", encoding="utf-8") as file:
        welcome = json.load(file)


    if request.method == "POST":

        welcome["enabled"] = "enabled" in request.form

        welcome["channel"] = request.form["channel"]

        welcome["message"] = request.form["message"]

        welcome["image_url"] = request.form["image_url"]

        welcome["banner_url"] = request.form["banner_url"]


        welcome["button"]["enabled"] = "button_enabled" in request.form

        welcome["button"]["text"] = request.form["button_text"]

        welcome["button"]["url"] = request.form["button_url"]


        welcome["dm"]["enabled"] = "dm_enabled" in request.form

        welcome["dm"]["message"] = request.form["dm_message"]


        with open(WELCOME_FILE, "w", encoding="utf-8") as file:
            json.dump(welcome, file, indent=4)

        apply_result = save_and_apply_feature("welcome", welcome)


    return render_template(
        "welcome.html",
        welcome=welcome
    )
@app.route("/tickets", methods=["GET", "POST"])
def tickets():
    default_ticket = {
        "enabled": True,
        "guild_id": "",
        "ticket_channel": "",
        "panel_message_id": "",
        "selection_type": "buttons",
        "option_count": 0,
        "panel": {
            "title": "🎟 Open a Ticket",
            "description": "Select the type of ticket you want to open.",
            "color": "991111",
            "placeholder": "Choose a ticket type...",
            "footer": "Pirates Bot Support",
            "image_url": "",
            "thumbnail_url": ""
        },
        "settings": {
            "close_message": "🔒 This ticket is now being closed.",
            "delete_after_close": True
        },
        "options": []
    }

    try:
        with open(TICKET_FILE, "r", encoding="utf-8") as file:
            ticket = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        ticket = default_ticket.copy()

    if not isinstance(ticket, dict):
        ticket = default_ticket.copy()

    ticket.setdefault("enabled", True)
    ticket.setdefault("guild_id", "")
    ticket.setdefault("ticket_channel", "")
    ticket.setdefault("panel_message_id", "")
    ticket.setdefault("selection_type", "buttons")
    ticket.setdefault("option_count", 0)
    ticket.setdefault("panel", {})
    ticket.setdefault("settings", {})
    ticket.setdefault("options", [])

    panel = ticket["panel"]
    panel.setdefault("title", "🎟 Open a Ticket")
    panel.setdefault(
        "description",
        "Select the type of ticket you want to open."
    )
    panel.setdefault("color", "991111")
    panel.setdefault("placeholder", "Choose a ticket type...")
    panel.setdefault("footer", "Pirates Bot Support")
    panel.setdefault("image_url", "")
    panel.setdefault("thumbnail_url", "")

    settings = ticket["settings"]
    settings.setdefault(
        "close_message",
        "🔒 This ticket is now being closed."
    )
    settings.setdefault("delete_after_close", True)

    if not isinstance(ticket["options"], list):
        ticket["options"] = []

    if request.method == "POST":
        ticket["enabled"] = "enabled" in request.form
        ticket["guild_id"] = str(
            session.get("selected_guild_id", "")
        )
        ticket["ticket_channel"] = request.form.get(
            "ticket_channel",
            ""
        ).strip()

        selection_type = request.form.get(
            "selection_type",
            "buttons"
        ).strip().lower()

        if selection_type not in {"buttons", "dropdown"}:
            selection_type = "buttons"

        ticket["selection_type"] = selection_type

        panel["title"] = request.form.get(
            "panel_title",
            "🎟 Open a Ticket"
        ).strip()

        panel["description"] = request.form.get(
            "panel_description",
            "Select the type of ticket you want to open."
        ).strip()

        panel["color"] = request.form.get(
            "panel_color",
            "991111"
        ).replace("#", "").strip()

        panel["placeholder"] = request.form.get(
            "panel_placeholder",
            "Choose a ticket type..."
        ).strip()

        panel["footer"] = request.form.get(
            "panel_footer",
            ""
        ).strip()

        panel["image_url"] = request.form.get(
            "panel_image_url",
            ""
        ).strip()

        panel["thumbnail_url"] = request.form.get(
            "panel_thumbnail_url",
            ""
        ).strip()

        settings["close_message"] = request.form.get(
            "close_message",
            "🔒 This ticket is now being closed."
        ).strip()

        settings["delete_after_close"] = (
            "delete_after_close" in request.form
        )

        try:
            option_count = int(
                request.form.get("option_count", "0")
            )
        except ValueError:
            option_count = 0

        option_count = max(0, min(option_count, 25))

        options = []

        for index in range(option_count):
            name = request.form.get(
                f"option_name_{index}",
                ""
            ).strip()

            if not name:
                continue

            option = {
                "enabled": (
                    f"option_enabled_{index}"
                    in request.form
                ),
                "name": name[:80],
                "emoji": request.form.get(
                    f"option_emoji_{index}",
                    "🎟"
                ).strip(),
                "description": request.form.get(
                    f"option_description_{index}",
                    ""
                ).strip()[:100],
                "button_color": request.form.get(
                    f"option_button_color_{index}",
                    "grey"
                ).strip().lower(),
                "embed_color": request.form.get(
                    f"option_embed_color_{index}",
                    "991111"
                ).replace("#", "").strip(),
                "category_id": request.form.get(
                    f"option_category_id_{index}",
                    ""
                ).strip(),
                "category_name": request.form.get(
                    f"option_category_name_{index}",
                    "Tickets"
                ).strip(),
                "staff_role_id": request.form.get(
                    f"option_staff_role_id_{index}",
                    ""
                ).strip(),
                "channel_prefix": request.form.get(
                    f"option_channel_prefix_{index}",
                    "ticket"
                ).strip(),
                "opening_message": request.form.get(
                    f"option_opening_message_{index}",
                    (
                        "Welcome {user}. Please explain "
                        "how we can help with your "
                        "{type} ticket."
                    )
                ).strip()
            }

            if option["button_color"] not in {
                "blue",
                "green",
                "red",
                "grey",
                "gray"
            }:
                option["button_color"] = "grey"

            options.append(option)

        ticket["options"] = options
        ticket["option_count"] = len(options)

        with open(TICKET_FILE, "w", encoding="utf-8") as file:
            json.dump(
                ticket,
                file,
                indent=4,
                ensure_ascii=False
            )

        apply_result = save_and_apply_feature("tickets", ticket)

        if apply_result and apply_result.get("ok"):
            flash(
                "Ticket settings saved and published.",
                "success"
            )
        else:
            error_message = (
                apply_result or {}
            ).get(
                "error",
                "Discord could not be updated."
            )

            flash(
                f"Ticket settings saved, but publishing failed: {error_message}",
                "warning"
            )

        return redirect(url_for("tickets"))

    return render_template(
        "tickets.html",
        ticket=ticket
    )


@app.route("/moderation", methods=["GET", "POST"])
def moderation():
    guild_id = str(
        session.get("selected_guild_id", "")
    ).strip()

    if not guild_id:
        return redirect(url_for("servers"))

    default_settings = {
        "enabled": False,
        "log_channel": "",
        "automod": {
            "enabled": False,
            "anti_spam": False,
            "anti_discord_links": False,
            "word_filter": False,
            "banned_words": []
        },
        "warnings": {
            "enabled": True,
            "max_warnings": 3
        },
        "kick": {
            "enabled": False
        },
        "ban": {
            "enabled": False
        },
        "mute": {
            "enabled": False,
            "duration": 10
        }
    }

    try:
        with open(
            MODERATION_FILE,
            "r",
            encoding="utf-8"
        ) as file:
            moderation_data = json.load(file)
    except (
        FileNotFoundError,
        json.JSONDecodeError,
        OSError
    ):
        moderation_data = {}

    if not isinstance(moderation_data, dict):
        moderation_data = {}

    # Convert the old global format into the new per-server format.
    if "guilds" not in moderation_data:
        old_settings = moderation_data

        moderation_data = {
            "guilds": {}
        }

        if old_settings.get("automod"):
            moderation_data["guilds"][guild_id] = old_settings

    guilds = moderation_data.setdefault("guilds", {})

    if not isinstance(guilds, dict):
        guilds = {}
        moderation_data["guilds"] = guilds

    moderation = guilds.setdefault(
        guild_id,
        default_settings.copy()
    )

    if not isinstance(moderation, dict):
        moderation = default_settings.copy()
        guilds[guild_id] = moderation

    moderation.setdefault("enabled", False)
    moderation.setdefault("log_channel", "")
    moderation.setdefault("automod", {})
    moderation.setdefault("warnings", {})
    moderation.setdefault("kick", {})
    moderation.setdefault("ban", {})
    moderation.setdefault("mute", {})

    automod = moderation["automod"]
    automod.setdefault("enabled", False)
    automod.setdefault("anti_spam", False)

    # Migrate the old anti_links setting.
    automod.setdefault(
        "anti_discord_links",
        automod.get("anti_links", False)
    )

    automod.pop("anti_links", None)

    automod.setdefault("word_filter", False)
    automod.setdefault("banned_words", [])
    automod.setdefault("allowed_discord_invites", [])

    if not isinstance(
        automod.get("banned_words"),
        list
    ):
        automod["banned_words"] = []
    
    if not isinstance(
        automod.get("allowed_discord_invites"),
        list
    ):
        automod["allowed_discord_invites"] = []  

    warnings = moderation["warnings"]
    warnings.setdefault("enabled", True)
    warnings.setdefault("max_warnings", 3)

    moderation["kick"].setdefault("enabled", False)
    moderation["ban"].setdefault("enabled", False)

    mute = moderation["mute"]
    mute.setdefault("enabled", False)
    mute.setdefault("duration", 10)

    if request.method == "POST":
        moderation["enabled"] = (
            "enabled" in request.form
        )

        moderation["log_channel"] = request.form.get(
            "log_channel",
            ""
        ).strip()

        automod["enabled"] = (
            "automod" in request.form
        )

        automod["anti_spam"] = (
            "anti_spam" in request.form
        )

        automod["anti_discord_links"] = (
            "anti_discord_links" in request.form
        )

        automod["word_filter"] = (
            "word_filter" in request.form
        )

        banned_words_text = request.form.get(
            "banned_words",
            ""
        )

        # Allow one word per line or comma-separated words.
        raw_words = banned_words_text.replace(
            "\r",
            "\n"
        ).replace(
            ",",
            "\n"
        ).split("\n")

        banned_words = []
        seen_words = set()

        for raw_word in raw_words:
            word = raw_word.strip().lower()

            if not word:
                continue

            if word in seen_words:
                continue

            seen_words.add(word)
            banned_words.append(word[:100])

        automod["banned_words"] = banned_words[:200]
        allowed_invites_text = request.form.get(
            "allowed_discord_invites",
            ""
        )

        raw_invites = allowed_invites_text.replace(
            "\r",
            "\n"
        ).replace(
            ",",
            "\n"
        ).split("\n")

        allowed_invites = []
        seen_invites = set()

        for raw_invite in raw_invites:
            invite = raw_invite.strip().lower()

            if not invite:
                continue

            invite = invite.replace(
                "https://",
                ""
            ).replace(
                "http://",
                ""
            ).replace(
                "www.",
                ""
            ).rstrip("/")

            if invite in seen_invites:
                continue

            if not (
                invite.startswith("discord.gg/")
                or invite.startswith(
                    "discord.com/invite/"
                )
                or invite.startswith(
                    "discordapp.com/invite/"
                )
            ):
                continue

            seen_invites.add(invite)
            allowed_invites.append(invite[:200])

        automod["allowed_discord_invites"] = (
            allowed_invites[:100]
        )

        warnings["enabled"] = (
            "warnings" in request.form
        )

        try:
            warnings["max_warnings"] = max(
                1,
                int(
                    request.form.get(
                        "max_warnings",
                        "3"
                    )
                )
            )
        except ValueError:
            warnings["max_warnings"] = 3

        moderation["kick"]["enabled"] = (
            "kick" in request.form
        )

        moderation["ban"]["enabled"] = (
            "ban" in request.form
        )

        mute["enabled"] = (
            "mute" in request.form
        )

        try:
            mute["duration"] = max(
                1,
                int(
                    request.form.get(
                        "mute_duration",
                        "10"
                    )
                )
            )
        except ValueError:
            mute["duration"] = 10

        guilds[guild_id] = moderation

        with open(
            MODERATION_FILE,
            "w",
            encoding="utf-8"
        ) as file:
            json.dump(
                moderation_data,
                file,
                indent=4,
                ensure_ascii=False
            )

        apply_result = save_and_apply_feature(
            "moderation",
            moderation_data
        )

        if not apply_result.get("ok"):
            flash(
                f"Moderation settings were saved locally, but the bot update failed: "
                f"{apply_result.get('error', 'Unknown error')}",
                "warning"
            )
        else:
            flash(
                "Moderation settings saved for this server.",
                "success"
            )

        return redirect(url_for("moderation"))

    return render_template(
        "moderation.html",
        moderation=moderation,
        banned_words_text="\n".join(
            automod.get("banned_words", [])
        ),
        allowed_invites_text="\n".join(
            automod.get(
                "allowed_discord_invites",
                []
            )
        ),
        selected_guild_id=guild_id
    )
@app.route(
    "/command-settings",
    methods=["GET", "POST"]
)
def command_settings():
    guild_id = str(
        session.get("selected_guild_id", "")
    ).strip()

    if not guild_id:
        return redirect(url_for("servers"))

    commands_data = bot_api_get(
        "/api/commands"
    ) or {
        "prefix_commands": [],
        "slash_commands": []
    }

    default_data = {
        "guilds": {}
    }

    command_permissions = load_or_create_json(
        COMMAND_PERMISSIONS_FILE,
        default_data
    )

    guilds = command_permissions.setdefault(
        "guilds",
        {}
    )

    guild_settings = guilds.setdefault(
        guild_id,
        {
            "commands": {}
        }
    )

    command_rules = guild_settings.setdefault(
        "commands",
        {}
    )

    all_commands = []

    for command in commands_data.get(
        "slash_commands",
        []
    ):
        all_commands.append({
            "name": command.get("name", ""),
            "description": command.get(
                "description",
                "No description"
            ),
            "type": "slash"
        })

    for command in commands_data.get(
        "prefix_commands",
        []
    ):
        command_name = command.get(
            "name",
            ""
        )

        if not any(
            existing["name"] == command_name
            for existing in all_commands
        ):
            all_commands.append({
                "name": command_name,
                "description": command.get(
                    "description",
                    "No description"
                ),
                "type": "prefix"
            })

    protected_staff_commands = {
        "ban",
        "kick",
        "mute",
        "unmute",
        "timeout",
        "untimeout",
        "purge",
        "clear",
        "warn",
        "warnings",
        "clearwarnings",
        "announce",
        "announcement",
        "giveaway",
        "reroll",
        "embed",
        "setup",
        "config",
        "settings",
        "reactionrole",
        "reactionroles",
        "ticketpanel",
        "sync",
        "reload",
        "shutdown",
        "addmoney",
        "removemoney",
        "economywipe",
        "roleadd",
        "roleremove",
    }

    for command in all_commands:
        command_name = command["name"].lower()

        default_access = (
            "staff"
            if command_name
            in protected_staff_commands
            else "everyone"
        )

        command_rules.setdefault(
            command_name,
            default_access
        )

    if request.method == "POST":
        for command in all_commands:
            command_name = command[
                "name"
            ].lower()

            selected_access = request.form.get(
                f"command_{command_name}",
                command_rules.get(
                    command_name,
                    "everyone"
                )
            )

            if command_name in protected_staff_commands:
                if selected_access == "everyone":
                    selected_access = "staff"

            if selected_access not in {
                "everyone",
                "staff",
                "disabled"
            }:
                selected_access = "everyone"

            command_rules[
                command_name
            ] = selected_access

        guild_settings[
            "commands"
        ] = command_rules

        guilds[
            guild_id
        ] = guild_settings

        with open(
            COMMAND_PERMISSIONS_FILE,
            "w",
            encoding="utf-8"
        ) as file:
            json.dump(
                command_permissions,
                file,
                indent=4,
                ensure_ascii=False
            )

        flash(
            "Command permissions saved for this server.",
            "success"
        )

        return redirect(
            url_for("command_settings")
        )

    member_commands = []
    admin_commands = []

    for command in all_commands:
        command_name = command[
            "name"
        ].lower()

        command["access"] = command_rules.get(
            command_name,
            "everyone"
        )

        command["protected"] = (
            command_name
            in protected_staff_commands
        )

        if command["protected"]:
            admin_commands.append(command)
        else:
            member_commands.append(command)

    member_commands.sort(
        key=lambda item: item["name"]
    )

    admin_commands.sort(
        key=lambda item: item["name"]
    )

    return render_template(
        "command_settings.html",
        member_commands=member_commands,
        admin_commands=admin_commands,
        selected_guild_id=guild_id
    )
        
@app.route("/settings", methods=["GET", "POST"])
def settings():

    with open(DASHBOARD_FILE, "r", encoding="utf-8") as file:
        dashboard = json.load(file)


    if request.method == "POST":

        dashboard["bot_name"] = request.form["bot_name"]
        dashboard["logo"] = request.form["logo"]
        dashboard["title"] = request.form["title"]
        dashboard["subtitle"] = request.form["subtitle"]
        dashboard["status"] = request.form["status"]
        dashboard["servers"] = request.form["servers"]
        dashboard["commands"] = request.form["commands"]
        dashboard["owner"] = request.form["owner"]


        with open(DASHBOARD_FILE, "w", encoding="utf-8") as file:
            json.dump(dashboard, file, indent=4)

        apply_result = save_and_apply_feature("settings", dashboard)


    return render_template(
    "settings.html",
    dashboard=dashboard
)
@app.route("/jobs", methods=["GET", "POST"])
def jobs():
    guild_id = str(
        session.get("selected_guild_id", "")
    ).strip()

    if not guild_id:
        return redirect(url_for("servers"))

    default_jobs = {
        "deckhand": {
            "name": "Deckhand",
            "emoji": "⚓",
            "description": "Maintain the ship and keep the decks seaworthy.",
            "min_pay": 100,
            "max_pay": 250,
            "risk": 0,
            "enabled": True
        },
        "fisherman": {
            "name": "Fisherman",
            "emoji": "🎣",
            "description": "Catch food and valuable sea creatures.",
            "min_pay": 150,
            "max_pay": 350,
            "risk": 5,
            "enabled": True
        },
        "merchant": {
            "name": "Merchant",
            "emoji": "🪙",
            "description": "Trade cargo between ports for profit.",
            "min_pay": 250,
            "max_pay": 500,
            "risk": 10,
            "enabled": True
        },
        "navigator": {
            "name": "Navigator",
            "emoji": "🧭",
            "description": "Guide pirate ships safely across dangerous waters.",
            "min_pay": 300,
            "max_pay": 600,
            "risk": 15,
            "enabled": True
        },
        "treasure_hunter": {
            "name": "Treasure Hunter",
            "emoji": "🗺️",
            "description": "Search lost islands for buried treasure.",
            "min_pay": 400,
            "max_pay": 900,
            "risk": 25,
            "enabled": True
        },
        "privateer": {
            "name": "Privateer",
            "emoji": "⚔️",
            "description": "Hunt enemy vessels under a captain's command.",
            "min_pay": 600,
            "max_pay": 1300,
            "risk": 35,
            "enabled": True
        }
    }

    jobs_data = load_or_create_json(
        JOBS_CONFIG_FILE,
        {
            "guilds": {}
        }
    )

    guilds = jobs_data.setdefault(
        "guilds",
        {}
    )

    jobs_settings = guilds.setdefault(
        guild_id,
        {
            "enabled": True,
            "daily_cooldown": 86400,
            "xp_min": 20,
            "xp_max": 45,
            "level_pay_bonus": 25,
            "jobs": default_jobs
        }
    )

    jobs_settings.setdefault("enabled", True)
    jobs_settings.setdefault("daily_cooldown", 86400)
    jobs_settings.setdefault("xp_min", 20)
    jobs_settings.setdefault("xp_max", 45)
    jobs_settings.setdefault("level_pay_bonus", 25)
    jobs_settings.setdefault("jobs", default_jobs)

    if not isinstance(
        jobs_settings.get("jobs"),
        dict
    ):
        jobs_settings["jobs"] = default_jobs

    for job_key, default_job in default_jobs.items():
        job = jobs_settings["jobs"].setdefault(
            job_key,
            default_job.copy()
        )

        for key, value in default_job.items():
            job.setdefault(key, value)

    if request.method == "POST":
        jobs_settings["enabled"] = (
            "enabled" in request.form
        )

        try:
            jobs_settings["daily_cooldown"] = max(
                0,
                int(
                    request.form.get(
                        "daily_cooldown",
                        "86400"
                    )
                )
            )
        except ValueError:
            jobs_settings["daily_cooldown"] = 86400

        try:
            jobs_settings["xp_min"] = max(
                1,
                int(
                    request.form.get(
                        "xp_min",
                        "20"
                    )
                )
            )
        except ValueError:
            jobs_settings["xp_min"] = 20

        try:
            jobs_settings["xp_max"] = max(
                jobs_settings["xp_min"],
                int(
                    request.form.get(
                        "xp_max",
                        "45"
                    )
                )
            )
        except ValueError:
            jobs_settings["xp_max"] = 45

        try:
            jobs_settings["level_pay_bonus"] = max(
                0,
                int(
                    request.form.get(
                        "level_pay_bonus",
                        "25"
                    )
                )
            )
        except ValueError:
            jobs_settings["level_pay_bonus"] = 25

        updated_jobs = {}

        for job_key, current_job in jobs_settings["jobs"].items():
            name = request.form.get(
                f"{job_key}_name",
                current_job.get("name", job_key.title())
            ).strip()

            emoji = request.form.get(
                f"{job_key}_emoji",
                current_job.get("emoji", "⚓")
            ).strip()

            description = request.form.get(
                f"{job_key}_description",
                current_job.get("description", "")
            ).strip()

            try:
                min_pay = max(
                    0,
                    int(
                        request.form.get(
                            f"{job_key}_min_pay",
                            current_job.get("min_pay", 0)
                        )
                    )
                )
            except ValueError:
                min_pay = int(
                    current_job.get("min_pay", 0)
                )

            try:
                max_pay = max(
                    min_pay,
                    int(
                        request.form.get(
                            f"{job_key}_max_pay",
                            current_job.get("max_pay", min_pay)
                        )
                    )
                )
            except ValueError:
                max_pay = int(
                    current_job.get("max_pay", min_pay)
                )

            try:
                risk = max(
                    0,
                    min(
                        100,
                        int(
                            request.form.get(
                                f"{job_key}_risk",
                                current_job.get("risk", 0)
                            )
                        )
                    )
                )
            except ValueError:
                risk = int(
                    current_job.get("risk", 0)
                )

            updated_jobs[job_key] = {
                "name": name[:80],
                "emoji": emoji[:32],
                "description": description[:300],
                "min_pay": min_pay,
                "max_pay": max_pay,
                "risk": risk,
                "enabled": (
                    f"{job_key}_enabled"
                    in request.form
                )
            }

        jobs_settings["jobs"] = updated_jobs
        guilds[guild_id] = jobs_settings

        with open(
            JOBS_CONFIG_FILE,
            "w",
            encoding="utf-8"
        ) as file:
            json.dump(
                jobs_data,
                file,
                indent=4,
                ensure_ascii=False
            )

        flash(
            "Pirate job settings saved for this server.",
            "success"
        )

        return redirect(url_for("jobs"))

    return render_template(
        "jobs.html",
        jobs_settings=jobs_settings,
        selected_guild_id=guild_id
    )
   
# =========================================================
# STICKY MESSAGES
# =========================================================

@app.route(
    "/sticky-messages",
    methods=["GET", "POST"]
)
def sticky_messages():
    guild_id = str(
        session.get(
            "selected_guild_id",
            ""
        )
    ).strip()

    if not guild_id:
        return redirect(
            url_for("servers")
        )

    sticky_data = load_or_create_json(
        STICKY_FILE,
        {
            "guilds": {}
        }
    )

    guilds = sticky_data.setdefault(
        "guilds",
        {}
    )

    guild_settings = guilds.setdefault(
        guild_id,
        {
            "channels": {}
        }
    )

    channels = guild_settings.setdefault(
        "channels",
        {}
    )

    if not isinstance(channels, dict):
        channels = {}
        guild_settings["channels"] = channels

    if request.method == "POST":
        action = request.form.get(
            "action",
            "save"
        ).strip().lower()

        channel_id = request.form.get(
            "channel_id",
            ""
        ).strip()

        if action == "delete":
            if channel_id:
                channels.pop(
                    channel_id,
                    None
                )

                guilds[guild_id] = guild_settings

                with open(
                    STICKY_FILE,
                    "w",
                    encoding="utf-8"
                ) as file:
                    json.dump(
                        sticky_data,
                        file,
                        indent=4,
                        ensure_ascii=False
                    )

                flash(
                    "Sticky message removed.",
                    "success"
                )

            return redirect(
                url_for("sticky_messages")
            )

        message_text = request.form.get(
            "message",
            ""
        ).strip()

        enabled = (
            "enabled"
            in request.form
        )

        if not channel_id:
            flash(
                "Please select a Discord channel.",
                "warning"
            )

            return redirect(
                url_for("sticky_messages")
            )

        if not message_text:
            flash(
                "Please enter a sticky message.",
                "warning"
            )

            return redirect(
                url_for("sticky_messages")
            )

        existing_settings = channels.get(
            channel_id,
            {}
        )

        channels[channel_id] = {
            "enabled": enabled,
            "message": message_text[:2000],
            "message_id": existing_settings.get(
                "message_id"
            )
        }

        guild_settings["channels"] = channels
        guilds[guild_id] = guild_settings

        with open(
            STICKY_FILE,
            "w",
            encoding="utf-8"
        ) as file:
            json.dump(
                sticky_data,
                file,
                indent=4,
                ensure_ascii=False
            )

        flash(
            "Sticky message saved for this server.",
            "success"
        )

        return redirect(
            url_for("sticky_messages")
        )

    return render_template(
        "sticky_messages.html",
        sticky_settings=guild_settings,
        sticky_channels=channels,
        selected_guild_id=guild_id
    )
# =========================================================
# AUTO ANNOUNCEMENTS
# =========================================================

@app.route(
    "/auto-announcements",
    methods=["GET", "POST"]
)
def auto_announcements():
    guild_id = str(
        session.get(
            "selected_guild_id",
            ""
        )
    ).strip()

    if not guild_id:
        return redirect(
            url_for("servers")
        )

    announcements_data = load_or_create_json(
        ANNOUNCEMENTS_FILE,
        {
            "guilds": {}
        }
    )

    guilds = announcements_data.setdefault(
        "guilds",
        {}
    )

    guild_settings = guilds.setdefault(
        guild_id,
        {
            "enabled": True,
            "announcements": []
        }
    )

    guild_settings.setdefault(
        "enabled",
        True
    )

    announcements = guild_settings.setdefault(
        "announcements",
        []
    )

    if not isinstance(announcements, list):
        announcements = []
        guild_settings["announcements"] = announcements

    if request.method == "POST":
        action = request.form.get(
            "action",
            "save"
        ).strip().lower()

        announcement_id = request.form.get(
            "announcement_id",
            ""
        ).strip()

        # Delete announcement
        if action == "delete":
            guild_settings["announcements"] = [
                announcement
                for announcement in announcements
                if str(
                    announcement.get(
                        "id",
                        ""
                    )
                ) != announcement_id
            ]

            guilds[guild_id] = guild_settings

            with open(
                ANNOUNCEMENTS_FILE,
                "w",
                encoding="utf-8"
            ) as file:
                json.dump(
                    announcements_data,
                    file,
                    indent=4,
                    ensure_ascii=False
                )

            flash(
                "Auto announcement deleted.",
                "success"
            )

            return redirect(
                url_for("auto_announcements")
            )

        channel_id = request.form.get(
            "channel_id",
            ""
        ).strip()

        message_text = request.form.get(
            "message",
            ""
        ).strip()

        try:
            interval_minutes = max(
                1,
                int(
                    request.form.get(
                        "interval_minutes",
                        "60"
                    )
                )
            )
        except ValueError:
            interval_minutes = 60

        interval_seconds = (
            interval_minutes * 60
        )

        enabled = (
            "enabled"
            in request.form
        )

        if not channel_id:
            flash(
                "Please select a Discord channel.",
                "warning"
            )

            return redirect(
                url_for("auto_announcements")
            )

        if not message_text:
            flash(
                "Please enter an announcement message.",
                "warning"
            )

            return redirect(
                url_for("auto_announcements")
            )

        existing_announcement = None

        for announcement in announcements:
            if str(
                announcement.get(
                    "id",
                    ""
                )
            ) == announcement_id:
                existing_announcement = announcement
                break

        if existing_announcement:
            existing_announcement.update({
                "enabled": enabled,
                "channel_id": channel_id,
                "message": message_text[:2000],
                "interval": interval_seconds
            })

        else:
            announcements.append({
                "id": secrets.token_hex(8),
                "enabled": enabled,
                "channel_id": channel_id,
                "message": message_text[:2000],
                "interval": interval_seconds,
                "last_sent": 0
            })

        guild_settings["announcements"] = announcements
        guilds[guild_id] = guild_settings

        with open(
            ANNOUNCEMENTS_FILE,
            "w",
            encoding="utf-8"
        ) as file:
            json.dump(
                announcements_data,
                file,
                indent=4,
                ensure_ascii=False
            )

        flash(
            "Auto announcement saved.",
            "success"
        )

        return redirect(
            url_for("auto_announcements")
        )

    return render_template(
        "auto_announcements.html",
        announcement_settings=guild_settings,
        announcements=announcements,
        selected_guild_id=guild_id
    )
# =========================================================
# REMINDERS
# =========================================================

@app.route(
    "/reminders",
    methods=["GET", "POST"]
)
def reminders():
    guild_id = str(
        session.get(
            "selected_guild_id",
            ""
        )
    ).strip()

    if not guild_id:
        return redirect(
            url_for("servers")
        )

    reminder_data = load_or_create_json(
        REMINDERS_FILE,
        {
            "reminders": []
        }
    )

    reminders = reminder_data.setdefault(
        "reminders",
        []
    )

    guild_reminders = [
        reminder
        for reminder in reminders
        if reminder.get("guild_id") == guild_id
    ]

    return render_template(
        "reminders.html",
        reminders=guild_reminders,
        selected_guild_id=guild_id
    )
# =========================================================
# ROLE MANAGER
# =========================================================

@app.route("/role-manager")
def role_manager():
    guild_id = str(
        session.get(
            "selected_guild_id",
            ""
        )
    ).strip()

    if not guild_id:
        return redirect(
            url_for("servers")
        )

    return render_template(
        "role_manager.html",
        selected_guild_id=guild_id
    )
# =========================================================
# LOGS
# =========================================================

@app.route(
    "/logs",
    methods=["GET", "POST"]
)
def logs():
    guild_id = str(
        session.get(
            "selected_guild_id",
            ""
        )
    ).strip()

    if not guild_id:
        return redirect(
            url_for("servers")
        )

    logs_data = load_or_create_json(
        LOGS_FILE,
        {
            "guilds": {}
        }
    )

    guild_logs = (
        logs_data.get("guilds", {})
        .get(guild_id, [])
    )

    if not isinstance(guild_logs, list):
        guild_logs = []

    if request.method == "POST":
        action = request.form.get(
            "action",
            ""
        ).strip().lower()

        if action == "clear":
            logs_data.setdefault(
                "guilds",
                {}
            )[guild_id] = []

            with open(
                LOGS_FILE,
                "w",
                encoding="utf-8"
            ) as file:
                json.dump(
                    logs_data,
                    file,
                    indent=4,
                    ensure_ascii=False
                )

            flash(
                "Logs cleared for this server.",
                "success"
            )

            return redirect(
                url_for("logs")
            )

    guild_logs = sorted(
        guild_logs,
        key=lambda item: float(
            item.get(
                "timestamp",
                0
            )
        ),
        reverse=True
    )

    return render_template(
        "logs.html",
        logs=guild_logs,
        selected_guild_id=guild_id
    )
# =========================
# EMBED BUILDER
# =========================

@app.route("/embeds", methods=["GET", "POST"])
def embeds():

    if not os.path.exists(EMBED_FILE):

        embed = {
            "enabled": False,
            "channel_id": "",
            "title": "",
            "description": "",
            "color": "#ff0000",
            "footer": "",
            "thumbnail": "",
            "image": ""
        }

        with open(EMBED_FILE, "w", encoding="utf-8") as file:
            json.dump(embed, file, indent=4)

        save_and_apply_feature("embeds", embed)


    with open(EMBED_FILE, "r", encoding="utf-8") as file:
        embed = json.load(file)



    if request.method == "POST":

        embed["enabled"] = "enabled" in request.form

        embed["channel_id"] = request.form.get(
            "channel_id",
            ""
        )

        embed["title"] = request.form.get(
            "title",
            ""
        )

        embed["description"] = request.form.get(
            "description",
            ""
        )

        embed["color"] = request.form.get(
            "color",
            "#ff0000"
        )

        embed["footer"] = request.form.get(
            "footer",
            ""
        )

        embed["thumbnail"] = request.form.get(
            "thumbnail",
            ""
        )

        embed["image"] = request.form.get(
            "image",
            ""
        )


        with open(EMBED_FILE, "w", encoding="utf-8") as file:
            json.dump(embed, file, indent=4)

        apply_result = save_and_apply_feature("embeds", embed)
        if not apply_result.get("ok"):
            flash(
                f"Embed settings were saved locally, but the bot update failed: "
                f"{apply_result.get('error', 'Unknown error')}",
                "warning"
            )


    return render_template(
        "embeds.html",
        embed=embed
    )



@app.route("/reaction-roles", methods=["GET", "POST"])
def reaction_roles():

    if not os.path.exists(REACTION_ROLE_FILE):

        roles = {

            "enabled": False,

            "channel_id": "",

            "message_id": "",

            "roles": []

        }


        with open(REACTION_ROLE_FILE, "w", encoding="utf-8") as file:
            json.dump(roles, file, indent=4)


    with open(REACTION_ROLE_FILE, "r", encoding="utf-8") as file:
        roles = json.load(file)


    if request.method == "POST":

        roles["enabled"] = "enabled" in request.form

        roles["channel_id"] = request.form.get(
            "channel_id",
            ""
        )

        roles["message_id"] = request.form.get(
            "message_id",
            ""
        )

        emoji = request.form.get(
            "emoji",
            ""
        )

        role_id = request.form.get(
            "role_id",
            ""
        )


        if emoji and role_id:
            roles["roles"].append({
                "emoji": emoji,
                "role_id": role_id
            })


        with open(REACTION_ROLE_FILE, "w", encoding="utf-8") as file:
            json.dump(
                roles,
                file,
                indent=4
            )

        apply_result = save_and_apply_feature("reaction_roles", roles)


    return render_template(
        "reaction_roles.html",
        roles=roles
    )
    
    
    
@app.route("/polls", methods=["GET", "POST"])
def polls():
    poll_data = load_or_create_json(POLL_FILE, {
        "channel_id": "",
        "title": "📊 Poll",
        "question": "",
        "color": "#5865F2",
        "footer": "",
        "message_id": ""
    })

    if request.method == "POST":
        poll_data["channel_id"] = request.form.get("channel_id", "").strip()
        poll_data["title"] = request.form.get("title", "📊 Poll").strip()
        poll_data["question"] = request.form.get("question", "").strip()
        poll_data["color"] = request.form.get("color", "#5865F2")
        poll_data["footer"] = request.form.get("footer", "").strip()
        poll_data["guild_id"] = str(session.get("selected_guild_id", ""))

        with open(POLL_FILE, "w", encoding="utf-8") as file:
            json.dump(poll_data, file, indent=4, ensure_ascii=False)

        result = save_and_apply_feature("polls", poll_data)
        if not result or not result.get("ok"):
            error = (result or {}).get("error", "The bot could not publish the poll.")
            return render_template("polls.html", poll=poll_data, publish_error=error), 400

        return redirect(url_for("polls", published="1"))

    return render_template("polls.html", poll=poll_data)


@app.route("/giveaways", methods=["GET", "POST"])
def giveaways():
    giveaway_data = load_or_create_json(GIVEAWAY_FILE, {
        "channel_id": "",
        "title": "🎉 Giveaway",
        "prize": "",
        "duration_seconds": 3600,
        "winner_count": 1,
        "color": "#F1C40F",
        "footer": "",
        "image_url": "",
        "message_id": ""
    })

    if request.method == "POST":
        giveaway_data["channel_id"] = request.form.get("channel_id", "").strip()
        giveaway_data["title"] = request.form.get("title", "🎉 Giveaway").strip()
        giveaway_data["prize"] = request.form.get("prize", "").strip()
        giveaway_data["duration_seconds"] = max(10, int(request.form.get("duration_seconds", 3600)))
        giveaway_data["winner_count"] = max(1, int(request.form.get("winner_count", 1)))
        giveaway_data["color"] = request.form.get("color", "#F1C40F")
        giveaway_data["footer"] = request.form.get("footer", "").strip()
        giveaway_data["image_url"] = request.form.get("image_url", "").strip()
        giveaway_data["guild_id"] = str(session.get("selected_guild_id", ""))

        with open(GIVEAWAY_FILE, "w", encoding="utf-8") as file:
            json.dump(giveaway_data, file, indent=4, ensure_ascii=False)

        result = save_and_apply_feature("giveaways", giveaway_data)
        if not result or not result.get("ok"):
            error = (result or {}).get("error", "The bot could not start the giveaway.")
            return render_template(
                "giveaways.html", giveaway=giveaway_data, publish_error=error
            ), 400

        return redirect(url_for("giveaways", published="1"))

    return render_template("giveaways.html", giveaway=giveaway_data)


@app.route("/rules", methods=["GET", "POST"])
def rules():

    if not os.path.exists(RULES_FILE):
        rules_data = {
            "menu": {
                "channel_id": "",
                "title": "🏴‍☠️ Pirates Server Rules",
                "description": "Choose a rules section below.",
                "color": "991111",
                "footer": "Pirates Bot Rules",
                "image_url": "",
                "thumbnail_url": ""
            },
            "sections": {}
        }

        with open(RULES_FILE, "w", encoding="utf-8") as file:
            json.dump(
                rules_data,
                file,
                indent=4,
                ensure_ascii=False
            )

    with open(RULES_FILE, "r", encoding="utf-8") as file:
        rules_data = json.load(file)

    if request.method == "POST":

        action = request.form.get("action", "save")

        menu = rules_data.setdefault("menu", {})
        sections = rules_data.setdefault("sections", {})

        # -------------------------
        # ADD A NEW RULE SECTION
        # -------------------------

        if action == "add_section":

            section_key = request.form.get(
                "new_section_key",
                ""
            ).strip().lower()

            section_key = section_key.replace(" ", "_")

            if section_key and section_key not in sections:
                sections[section_key] = {
                    "button_label": "New Rules",
                    "button_emoji": "📜",
                    "title": "📜 New Rules",
                    "description": "Add your rules here.",
                    "color": "991111",
                    "image_url": "",
                    "thumbnail_url": ""
                }

        # -------------------------
        # DELETE A RULE SECTION
        # -------------------------

        elif action == "delete_section":

            section_key = request.form.get(
                "section_key",
                ""
            )

            sections.pop(section_key, None)

        # -------------------------
        # SAVE ALL SETTINGS
        # -------------------------

        else:

            menu["channel_id"] = request.form.get(
                "menu_channel_id",
                ""
            )

            menu["title"] = request.form.get(
                "menu_title",
                "🏴‍☠️ Pirates Server Rules"
            )

            menu["description"] = request.form.get(
                "menu_description",
                ""
            )

            menu["color"] = request.form.get(
                "menu_color",
                "991111"
            ).replace("#", "")

            menu["footer"] = request.form.get(
                "menu_footer",
                ""
            )

            menu["image_url"] = request.form.get(
                "menu_image_url",
                ""
            )

            menu["thumbnail_url"] = request.form.get(
                "menu_thumbnail_url",
                ""
            )

            for section_key, section in sections.items():

                section["button_label"] = request.form.get(
                    f"{section_key}_button_label",
                    section.get(
                        "button_label",
                        section_key.title()
                    )
                )

                section["button_emoji"] = request.form.get(
                    f"{section_key}_button_emoji",
                    section.get("button_emoji", "")
                )

                section["title"] = request.form.get(
                    f"{section_key}_title",
                    section.get(
                        "title",
                        section_key.title()
                    )
                )

                section["description"] = request.form.get(
                    f"{section_key}_description",
                    section.get("description", "")
                )

                section["color"] = request.form.get(
                    f"{section_key}_color",
                    section.get("color", "991111")
                ).replace("#", "")

                section["image_url"] = request.form.get(
                    f"{section_key}_image_url",
                    section.get("image_url", "")
                )

                section["thumbnail_url"] = request.form.get(
                    f"{section_key}_thumbnail_url",
                    section.get("thumbnail_url", "")
                )

        with open(RULES_FILE, "w", encoding="utf-8") as file:
            json.dump(
                rules_data,
                file,
                indent=4,
                ensure_ascii=False
            )

        save_and_apply_feature("rules", rules_data)
        return redirect("/rules")

    return render_template(
        "rules.html",
        rules=rules_data
    )



DEADSIDE_DEFAULTS = {
    "enabled": False,
    "guild_id": "",
    "server_name": "My Deadside Server",
    "provider": "gportal",
    "connection_method": "ftps",
    "protocol": "ftps",
    "host": "",
    "port": 21,
    "username": "",
    "password": "",
    "server_ip": "",
    "game_port": 0,
    "query_port": 0,
    "rcon_port": 0,
    "password_configured": False,
    "deadside_log_path": "",
    "death_logs_directory": "",
    "admin_logs_directory": "",
    "admin_log_file_pattern": "*.log,*.txt,*.csv",
    "log_file_pattern": "*.log,*.txt,*.csv,*.json",
    "max_log_files": 5,
    "feed_url": "",
    "auth_header": "Authorization",
    "auth_token": "",
    "poll_interval": 60,
    "killfeed_channel": "",
    "leaderboard_channel": "",
    "status_channel": "",
    "activity_channel": "",
    "admin_log_channel": "",
    "admin_logs_enabled": False,
    "admin_show_spawns": True,
    "admin_show_vehicles": True,
    "admin_show_teleports": True,
    "admin_show_kicks": True,
    "admin_show_bans": True,
    "admin_show_godmode": True,
    "admin_show_coordinates": True,
    "show_weapon": True,
    "show_distance": True,
    "show_headshots": True,
    "show_suicides": True,
    "show_ai_kills": True,
    "show_safezone_deaths": True,
    "show_vehicle_kills": True,
    "embed_title": "☠️ Deadside Killfeed",
    "embed_color": "991111",
    "embed_footer": "",
    "embed_thumbnail": "",
    "leaderboard_enabled": True,
    "leaderboard_limit": 10,
    "leaderboard_interval": 300,
    "leaderboard_title": "🏆 Deadside Leaderboard",
    "track_kills": True,
    "track_deaths": True,
    "track_kd": True,
    "track_longest_kill": True,
    "track_favorite_weapon": True,
    "track_killstreak": True,
    "player_linking_enabled": True,
    "player_rewards_enabled": False,
    "pay_per_kill": 25,
    "minimum_kill_payment": 0,
    "maximum_kill_payment": 250,
    "headshot_bonus": 10,
    "session_payment_limit": 1000,
    "reward_session_minutes": 120,
    "reward_notifications": False,
    "player_bounties_enabled": True,
    "minimum_bounty": 100,
    "maximum_bounty": 10000,
    "maximum_active_bounties": 3,
    "bounty_expiry_hours": 72,
    "refund_expired_bounties": True,
    "killstreak_bounties_enabled": True,
    "killstreak_bounty_start": 5,
    "killstreak_bounty_every": 5,
    "killstreak_bounty_reward": 250,
    "killstreak_bounty_increase": 50,
    "killstreak_bounty_maximum": 5000,
    "radar_enabled": False,
    "radar_channel": "",
    "radar_minimum_streak": 5,
    "duplicate_protection": True,
    "debug_logging": False,
    "auto_reconnect": True,
    "factions": [],
    "faction_settings": {
        "enabled": True,
        "allow_multiple_memberships": False,
        "show_flags_in_killfeed": True,
        "show_faction_names_in_killfeed": True
    },
    "kill_pattern": r"(?P<killer>.+?)\\s+(?:killed|eliminated)\\s+(?P<victim>.+?)(?:\\s+with\\s+(?P<weapon>.+?))?(?:\\s+at\\s+(?P<distance>\\d+(?:\\.\\d+)?)m)?$",
}


def load_deadside_settings():
    guild_id = str(session.get("selected_guild_id", ""))
    if not guild_id:
        return "", DEADSIDE_DEFAULTS.copy()
    settings = DEADSIDE_DEFAULTS.copy()
    settings["guild_id"] = guild_id
    remote = bot_api_get(f"/api/dashboard/settings/deadside/{guild_id}") or {}
    if isinstance(remote, dict) and isinstance(remote.get("settings"), dict):
        settings.update(remote["settings"])
    return guild_id, settings


def save_deadside_settings(settings):
    result = save_and_apply_feature("deadside", settings)
    if result and result.get("ok"):
        flash(result.get("message", "Deadside settings saved."), "success")
    else:
        flash(
            f"Deadside settings were not applied: {(result or {}).get('error', 'Unknown error')}",
            "warning",
        )
    return result


def require_deadside_guild():
    guild_id, settings = load_deadside_settings()
    if not guild_id:
        flash("Select a Discord server first.", "warning")
        return None, None
    return guild_id, settings


@app.route("/integrations")
def integrations():
    return render_template("integrations.html")


@app.route("/integrations/deadside")
def deadside_overview():
    guild_id, settings = require_deadside_guild()
    if not guild_id:
        return redirect(url_for("servers"))
    return render_template("deadside/overview.html", deadside=settings, deadside_tab="overview")


@app.route("/integrations/deadside/connection", methods=["GET", "POST"])
def deadside_connection():
    guild_id, settings = require_deadside_guild()
    if not guild_id:
        return redirect(url_for("servers"))

    settings["provider"] = "gportal"
    settings["connection_method"] = "ftps"
    settings["protocol"] = "ftps"

    if request.method == "POST":
        settings.update({
            "enabled": "enabled" in request.form,
            "guild_id": guild_id,
            "server_name": request.form.get(
                "server_name",
                "My Deadside Server"
            ).strip(),
            "provider": "gportal",
            "connection_method": "ftps",
            "protocol": "ftps",
            "host": request.form.get("host", "").strip(),
            "username": request.form.get("username", "").strip(),
            "password": request.form.get("password", ""),
            "server_ip": request.form.get("server_ip", "").strip(),
            "deadside_log_path": request.form.get(
                "deadside_log_path",
                ""
            ).strip(),
            "death_logs_directory": request.form.get(
                "death_logs_directory",
                ""
            ).strip(),
            "log_file_pattern": request.form.get(
                "log_file_pattern",
                "*.log,*.txt,*.csv,*.json"
            ).strip(),
            "auto_reconnect": "auto_reconnect" in request.form,
        })

        try:
            settings["port"] = max(
                1,
                min(int(request.form.get("port", "21") or 21), 65535)
            )
        except ValueError:
            settings["port"] = 21

        try:
            settings["poll_interval"] = max(
                30,
                min(
                    int(request.form.get("poll_interval", "60") or 60),
                    900
                )
            )
        except ValueError:
            settings["poll_interval"] = 60

        try:
            settings["max_log_files"] = max(
                1,
                min(
                    int(request.form.get("max_log_files", "5") or 5),
                    25
                )
            )
        except ValueError:
            settings["max_log_files"] = 5

        save_deadside_settings(settings)
        return redirect(url_for("deadside_connection"))

    return render_template(
        "deadside/connection.html",
        deadside=settings,
        deadside_tab="connection"
    )


@app.route("/integrations/deadside/channels", methods=["GET", "POST"])
def deadside_channels():
    guild_id, settings = require_deadside_guild()
    if not guild_id:
        return redirect(url_for("servers"))
    if request.method == "POST":
        for key in ("killfeed_channel", "leaderboard_channel", "status_channel", "activity_channel", "admin_log_channel"):
            settings[key] = request.form.get(key, "").strip()
        save_deadside_settings(settings)
        return redirect(url_for("deadside_channels"))
    return render_template("deadside/channels.html", deadside=settings, deadside_tab="channels")


@app.route("/integrations/deadside/killfeed", methods=["GET", "POST"])
def deadside_killfeed():
    guild_id, settings = require_deadside_guild()
    if not guild_id:
        return redirect(url_for("servers"))
    if request.method == "POST":
        for key in ("show_weapon", "show_distance", "show_headshots", "show_suicides", "show_ai_kills", "show_safezone_deaths", "show_vehicle_kills"):
            settings[key] = key in request.form
        settings["embed_title"] = request.form.get("embed_title", "☠️ Deadside Killfeed").strip()
        settings["embed_color"] = request.form.get("embed_color", "991111").replace("#", "").strip()
        settings["embed_footer"] = request.form.get("embed_footer", "").strip()
        settings["embed_thumbnail"] = request.form.get("embed_thumbnail", "").strip()
        settings["kill_pattern"] = request.form.get("kill_pattern", DEADSIDE_DEFAULTS["kill_pattern"]).strip()
        save_deadside_settings(settings)
        return redirect(url_for("deadside_killfeed"))
    return render_template("deadside/killfeed.html", deadside=settings, deadside_tab="killfeed")



DEADSIDE_FLAG_PRESETS = [
    {"value": "flag_01", "image": "/static/images/deadside_flags/flag_01.png"},
    {"value": "flag_02", "image": "/static/images/deadside_flags/flag_02.png"},
    {"value": "flag_03", "image": "/static/images/deadside_flags/flag_03.png"},
    {"value": "flag_04", "image": "/static/images/deadside_flags/flag_04.png"},
    {"value": "flag_05", "image": "/static/images/deadside_flags/flag_05.png"},
    {"value": "flag_06", "image": "/static/images/deadside_flags/flag_06.png"},
    {"value": "flag_07", "image": "/static/images/deadside_flags/flag_07.png"},
    {"value": "flag_08", "image": "/static/images/deadside_flags/flag_08.png"},
    {"value": "flag_09", "image": "/static/images/deadside_flags/flag_09.png"},
    {"value": "flag_10", "image": "/static/images/deadside_flags/flag_10.png"},
    {"value": "flag_11", "image": "/static/images/deadside_flags/flag_11.png"},
    {"value": "flag_12", "image": "/static/images/deadside_flags/flag_12.png"},
    {"value": "flag_13", "image": "/static/images/deadside_flags/flag_13.png"},
    {"value": "flag_14", "image": "/static/images/deadside_flags/flag_14.png"},
    {"value": "flag_15", "image": "/static/images/deadside_flags/flag_15.png"},
    {"value": "flag_16", "image": "/static/images/deadside_flags/flag_16.png"},
    {"value": "flag_17", "image": "/static/images/deadside_flags/flag_17.png"},
    {"value": "flag_18", "image": "/static/images/deadside_flags/flag_18.png"},
    {"value": "flag_19", "image": "/static/images/deadside_flags/flag_19.png"},
    {"value": "flag_20", "image": "/static/images/deadside_flags/flag_20.png"},
    {"value": "flag_21", "image": "/static/images/deadside_flags/flag_21.png"},
    {"value": "flag_22", "image": "/static/images/deadside_flags/flag_22.png"},
    {"value": "flag_23", "image": "/static/images/deadside_flags/flag_23.png"},
    {"value": "flag_24", "image": "/static/images/deadside_flags/flag_24.png"},
    {"value": "flag_25", "image": "/static/images/deadside_flags/flag_25.png"},
    {"value": "flag_26", "image": "/static/images/deadside_flags/flag_26.png"},
    {"value": "flag_27", "image": "/static/images/deadside_flags/flag_27.png"},
    {"value": "flag_28", "image": "/static/images/deadside_flags/flag_28.png"},
    {"value": "flag_29", "image": "/static/images/deadside_flags/flag_29.png"},
    {"value": "flag_30", "image": "/static/images/deadside_flags/flag_30.png"},
]


def _normalise_deadside_factions(settings):
    factions = settings.get("factions", [])
    if not isinstance(factions, list):
        factions = []

    cleaned = []
    for item in factions:
        if not isinstance(item, dict):
            continue
        faction = dict(item)
        faction.setdefault("id", secrets.token_urlsafe(8))
        faction.setdefault("name", "Unnamed Faction")
        faction.setdefault("leader_id", "")
        faction.setdefault("member_ids", [])
        faction.setdefault("role_id", "")
        faction.setdefault("flag", "flag_01")
        faction.setdefault("flag_image", "/static/images/deadside_flags/flag_01.png")
        faction.setdefault("custom_flag_url", "")
        faction.setdefault("channel_id", "")
        faction.setdefault("message_id", "")
        faction.setdefault("color", "991111")
        faction.setdefault("description", "")
        faction.setdefault("enabled", True)
        if not isinstance(faction["member_ids"], list):
            faction["member_ids"] = []
        faction["member_ids"] = [str(value) for value in faction["member_ids"]]
        cleaned.append(faction)

    settings["factions"] = cleaned
    settings.setdefault("faction_settings", {
        "enabled": True,
        "allow_multiple_memberships": False,
        "show_flags_in_killfeed": True,
        "show_faction_names_in_killfeed": True,
    })
    return cleaned


@app.route("/integrations/deadside/factions", methods=["GET", "POST"])
def deadside_factions():
    guild_id, settings = require_deadside_guild()
    if not guild_id:
        return redirect(url_for("servers"))

    factions = _normalise_deadside_factions(settings)
    action = request.form.get("action", "").strip().lower()

    if request.method == "POST":
        faction_settings = settings.setdefault("faction_settings", {})
        faction_settings["enabled"] = "factions_enabled" in request.form
        faction_settings["allow_multiple_memberships"] = (
            "allow_multiple_memberships" in request.form
        )
        faction_settings["show_flags_in_killfeed"] = (
            "show_flags_in_killfeed" in request.form
        )
        faction_settings["show_faction_names_in_killfeed"] = (
            "show_faction_names_in_killfeed" in request.form
        )

        if action == "delete":
            faction_id = request.form.get("faction_id", "").strip()
            settings["factions"] = [
                faction
                for faction in factions
                if str(faction.get("id")) != faction_id
            ]
            save_deadside_settings(settings)
            return redirect(url_for("deadside_factions"))

        if action in {"create", "update", "publish"}:
            faction_id = request.form.get("faction_id", "").strip()
            target = None

            if action in {"update", "publish"} and faction_id:
                target = next(
                    (
                        faction
                        for faction in factions
                        if str(faction.get("id")) == faction_id
                    ),
                    None
                )

            if target is None:
                target = {
                    "id": secrets.token_urlsafe(8),
                    "member_ids": [],
                }
                factions.append(target)

            selected_flag = request.form.get("flag", "flag_01")
            preset = next(
                (
                    flag
                    for flag in DEADSIDE_FLAG_PRESETS
                    if flag["value"] == selected_flag
                ),
                {
                    "value": "flag_01",
                    "image": "/static/images/deadside_flags/flag_01.png"
                }
            )

            leader_id = request.form.get("leader_id", "").strip()
            member_ids = [
                str(value).strip()
                for value in request.form.getlist("member_ids")
                if str(value).strip()
            ]
            if leader_id and leader_id not in member_ids:
                member_ids.insert(0, leader_id)

            target.update({
                "name": request.form.get(
                    "faction_name",
                    "Unnamed Faction"
                ).strip()[:80],
                "leader_id": leader_id,
                "member_ids": list(dict.fromkeys(member_ids)),
                "role_id": request.form.get("role_id", "").strip(),
                "flag": preset["value"],
                "flag_image": preset["image"],
                "channel_id": request.form.get("channel_id", "").strip(),
                "message_id": target.get("message_id", ""),
                "custom_flag_url": request.form.get(
                    "custom_flag_url",
                    ""
                ).strip(),
                "color": request.form.get(
                    "color",
                    "991111"
                ).replace("#", "").strip()[:6],
                "description": request.form.get(
                    "description",
                    ""
                ).strip()[:500],
                "enabled": "faction_enabled" in request.form,
            })

            settings["factions"] = factions
            save_deadside_settings(settings)

            if action == "publish":
                publish_result = bot_api_post(
                    f"/api/deadside/faction/{guild_id}/{target['id']}/publish"
                )
                if publish_result and publish_result.get("ok"):
                    flash(
                        publish_result.get(
                            "message",
                            "Faction embed published."
                        ),
                        "success"
                    )
                else:
                    flash(
                        (publish_result or {}).get(
                            "error",
                            "Faction saved, but the embed could not be published."
                        ),
                        "error"
                    )

            return redirect(url_for("deadside_factions"))

        save_deadside_settings(settings)
        return redirect(url_for("deadside_factions"))

    members = bot_api_get(f"/api/guild/{guild_id}/members") or []
    roles = bot_api_get(f"/api/guild/{guild_id}/roles") or []
    channels = bot_api_get(f"/api/guild/{guild_id}/channels") or []
    text_channels = [
        channel
        for channel in channels
        if channel.get("type") in {"text", "news", "forum"}
    ]

    return render_template(
        "deadside/factions.html",
        deadside=settings,
        factions=factions,
        faction_settings=settings.get("faction_settings", {}),
        flag_presets=DEADSIDE_FLAG_PRESETS,
        members=members,
        roles=roles,
        channels=text_channels,
        deadside_tab="factions",
    )



@app.route("/integrations/deadside/leaderboards", methods=["GET", "POST"])
def deadside_leaderboards():
    guild_id, settings = require_deadside_guild()
    if not guild_id:
        return redirect(url_for("servers"))
    if request.method == "POST":
        settings["leaderboard_enabled"] = "leaderboard_enabled" in request.form
        settings["leaderboard_title"] = request.form.get("leaderboard_title", "🏆 Deadside Leaderboard").strip()
        try:
            settings["leaderboard_limit"] = max(3, min(int(request.form.get("leaderboard_limit", "10")), 25))
        except ValueError:
            settings["leaderboard_limit"] = 10
        try:
            settings["leaderboard_interval"] = max(60, min(int(request.form.get("leaderboard_interval", "300")), 86400))
        except ValueError:
            settings["leaderboard_interval"] = 300
        save_deadside_settings(settings)
        return redirect(url_for("deadside_leaderboards"))
    return render_template("deadside/leaderboards.html", deadside=settings, deadside_tab="leaderboards")


@app.route("/integrations/deadside/statistics", methods=["GET", "POST"])
def deadside_statistics():
    guild_id, settings = require_deadside_guild()
    if not guild_id:
        return redirect(url_for("servers"))

    if request.method == "POST":
        checkbox_keys = (
            "track_kills",
            "track_deaths",
            "track_kd",
            "track_longest_kill",
            "track_favorite_weapon",
            "track_killstreak",
            "player_linking_enabled",
            "player_rewards_enabled",
            "reward_notifications",
            "player_bounties_enabled",
            "refund_expired_bounties",
            "killstreak_bounties_enabled",
            "radar_enabled",
        )
        for key in checkbox_keys:
            settings[key] = key in request.form

        integer_fields = {
            "pay_per_kill": (0, 100000),
            "minimum_kill_payment": (0, 100000),
            "maximum_kill_payment": (0, 100000),
            "headshot_bonus": (0, 100000),
            "session_payment_limit": (0, 10000000),
            "reward_session_minutes": (5, 1440),
            "minimum_bounty": (1, 10000000),
            "maximum_bounty": (1, 100000000),
            "maximum_active_bounties": (1, 25),
            "bounty_expiry_hours": (1, 8760),
            "killstreak_bounty_start": (2, 1000),
            "killstreak_bounty_every": (1, 1000),
            "killstreak_bounty_reward": (0, 10000000),
            "killstreak_bounty_increase": (0, 10000000),
            "killstreak_bounty_maximum": (0, 100000000),
            "radar_minimum_streak": (1, 1000),
        }
        for key, (minimum, maximum) in integer_fields.items():
            try:
                value = int(request.form.get(key, settings.get(key, minimum)))
            except (TypeError, ValueError):
                value = int(settings.get(key, minimum) or minimum)
            settings[key] = max(minimum, min(value, maximum))

        settings["radar_channel"] = request.form.get(
            "radar_channel",
            ""
        ).strip()

        if settings["maximum_kill_payment"] < settings["minimum_kill_payment"]:
            settings["maximum_kill_payment"] = settings["minimum_kill_payment"]
        if settings["maximum_bounty"] < settings["minimum_bounty"]:
            settings["maximum_bounty"] = settings["minimum_bounty"]
        if settings["killstreak_bounty_maximum"] < settings["killstreak_bounty_reward"]:
            settings["killstreak_bounty_maximum"] = settings["killstreak_bounty_reward"]

        save_deadside_settings(settings)
        return redirect(url_for("deadside_statistics"))

    channels = bot_api_get(f"/api/guild/{guild_id}/channels") or []
    text_channels = [
        channel
        for channel in channels
        if channel.get("type") in {"text", "news", "forum"}
    ]
    return render_template(
        "deadside/statistics.html",
        deadside=settings,
        channels=text_channels,
        deadside_tab="statistics",
    )


@app.route("/integrations/deadside/advanced", methods=["GET", "POST"])
def deadside_advanced():
    guild_id, settings = require_deadside_guild()
    if not guild_id:
        return redirect(url_for("servers"))
    if request.method == "POST":
        settings["duplicate_protection"] = "duplicate_protection" in request.form
        settings["debug_logging"] = "debug_logging" in request.form
        settings["auto_reconnect"] = "auto_reconnect" in request.form
        save_deadside_settings(settings)
        return redirect(url_for("deadside_advanced"))
    return render_template("deadside/advanced.html", deadside=settings, deadside_tab="advanced")



# =================== DAYZ DASHBOARD ===================
DAYZ_DEFAULTS={"enabled":False,"guild_id":"","server_name":"My DayZ Server","platform":"pc","map_name":"Chernarus","map_size":15360,"nitrado_api_base":"https://api.nitrado.net","nitrado_service_id":"","nitrado_api_token":"","ftp_host":"","ftp_port":21,"ftp_username":"","ftp_password":"","admin_log_path":"","poll_interval":60,"killfeed_channel":"","deathfeed_channel":"","bounty_channel":"","killfeed_title":"☠️ DayZ Killfeed","deathfeed_title":"💀 DayZ Deathfeed","embed_color":"991111","show_weapon":True,"show_distance":True,"show_location":True,"pay_per_kill_enabled":False,"pay_per_kill":25,"minimum_bounty":100,"maximum_bounty":10000,"radar_enabled":False,"radar_channel":"","radar_ping_role":"","radar_center_x":7500,"radar_center_z":7500,"radar_radius":1000,"radar_interval_seconds":600,"factions":[]}

def load_dayz_settings():
    gid=str(session.get("selected_guild_id",""))
    if not gid:return "",DAYZ_DEFAULTS.copy()
    s=DAYZ_DEFAULTS.copy();s["guild_id"]=gid;remote=bot_api_get(f"/api/dashboard/settings/dayz/{gid}") or {}
    if isinstance(remote,dict) and isinstance(remote.get("settings"),dict):s.update(remote["settings"])
    return gid,s

def save_dayz_settings(s):
    result=save_and_apply_feature("dayz",s)
    if result and result.get("ok"):flash(result.get("message","DayZ settings saved."),"success")
    else:flash(f"DayZ settings were not applied: {(result or {}).get('error','Unknown error')}","warning")
    return result

def require_dayz_guild():
    gid,s=load_dayz_settings()
    if not gid:return None,None
    if not can_manage_guild(gid):abort(403)
    return gid,s

@app.route("/integrations/dayz")
def dayz_overview():
    gid,s=require_dayz_guild()
    if not gid:return redirect(url_for("servers"))
    return render_template("dayz/overview.html",dayz=s,dayz_tab="overview")

@app.route("/integrations/dayz/connection",methods=["GET","POST"])
def dayz_connection():
    gid,s=require_dayz_guild()
    if not gid:return redirect(url_for("servers"))
    if request.method=="POST":
        s.update({"enabled":"enabled" in request.form,"guild_id":gid,"server_name":request.form.get("server_name","My DayZ Server").strip(),"platform":request.form.get("platform","pc").strip(),"map_name":request.form.get("map_name","Chernarus").strip(),"nitrado_service_id":request.form.get("nitrado_service_id","").strip(),"nitrado_api_token":request.form.get("nitrado_api_token",""),"ftp_host":request.form.get("ftp_host","").strip(),"ftp_username":request.form.get("ftp_username","").strip(),"ftp_password":request.form.get("ftp_password",""),"admin_log_path":request.form.get("admin_log_path","").strip()})
        for key,default,lo,hi in (("ftp_port",21,1,65535),("poll_interval",60,30,900),("map_size",15360,1000,100000)):
            try:s[key]=max(lo,min(int(request.form.get(key,default) or default),hi))
            except ValueError:s[key]=default
        save_dayz_settings(s);return redirect(url_for("dayz_connection"))
    return render_template("dayz/connection.html",dayz=s,dayz_tab="connection")

@app.route("/integrations/dayz/feeds",methods=["GET","POST"])
def dayz_feeds():
    gid,s=require_dayz_guild();channels=bot_api_get(f"/api/guild/{gid}/channels") or []; channels=[c for c in channels if c.get("type") in {"text","news","forum"}]
    if request.method=="POST":
        for k in ("killfeed_channel","deathfeed_channel","bounty_channel"):s[k]=request.form.get(k,"").strip()
        for k in ("show_weapon","show_distance","show_location"):s[k]=k in request.form
        s["killfeed_title"]=request.form.get("killfeed_title","☠️ DayZ Killfeed").strip();s["deathfeed_title"]=request.form.get("deathfeed_title","💀 DayZ Deathfeed").strip();s["embed_color"]=request.form.get("embed_color","991111").replace("#","").strip();save_dayz_settings(s);return redirect(url_for("dayz_feeds"))
    return render_template("dayz/feeds.html",dayz=s,channels=channels,dayz_tab="feeds")

@app.route("/integrations/dayz/radar",methods=["GET","POST"])
def dayz_radar():
    gid,s=require_dayz_guild();channels=bot_api_get(f"/api/guild/{gid}/channels") or [];roles=bot_api_get(f"/api/guild/{gid}/roles") or [];channels=[c for c in channels if c.get("type") in {"text","news","forum"}]
    if request.method=="POST":
        s["radar_enabled"]="radar_enabled" in request.form;s["radar_channel"]=request.form.get("radar_channel","").strip();s["radar_ping_role"]=request.form.get("radar_ping_role","").strip()
        for k,d,lo,hi in (("radar_center_x",7500,0,100000),("radar_center_z",7500,0,100000),("radar_radius",1000,1,50000),("radar_interval_seconds",600,60,3600)):
            try:s[k]=max(lo,min(int(request.form.get(k,d) or d),hi))
            except ValueError:s[k]=d
        save_dayz_settings(s);return redirect(url_for("dayz_radar"))
    return render_template("dayz/radar.html",dayz=s,channels=channels,roles=roles,dayz_tab="radar")

@app.route("/integrations/dayz/economy",methods=["GET","POST"])
def dayz_economy():
    gid,s=require_dayz_guild()
    if request.method=="POST":
        s["pay_per_kill_enabled"]="pay_per_kill_enabled" in request.form
        for k,d,lo,hi in (("pay_per_kill",25,0,1000000),("minimum_bounty",100,1,100000000),("maximum_bounty",10000,1,100000000)):
            try:s[k]=max(lo,min(int(request.form.get(k,d) or d),hi))
            except ValueError:s[k]=d
        s["maximum_bounty"]=max(s["minimum_bounty"],s["maximum_bounty"]);save_dayz_settings(s);return redirect(url_for("dayz_economy"))
    return render_template("dayz/economy.html",dayz=s,dayz_tab="economy")

@app.route("/integrations/dayz/shop", methods=["GET", "POST"])
def dayz_shop():
    guild_id, settings = require_dayz_guild()
    if not guild_id:
        return redirect(url_for("servers"))

    shop_path = os.path.join(BASE_DIR, "dayz_shop.json")
    root = load_or_create_json(shop_path, {"guilds": {}})
    guild_shop = root.setdefault("guilds", {}).setdefault(
        str(guild_id),
        {"items": [], "vehicles": []}
    )
    guild_shop.setdefault("items", [])
    guild_shop.setdefault("vehicles", [])

    if request.method == "POST":
        action = request.form.get("action", "").strip()

        if action in {"add_item", "update_item"}:
            key = request.form.get("key", "").strip()
            if not key:
                flash("Shop item key is required.", "warning")
                return redirect(url_for("dayz_shop"))

            try:
                price = max(0, int(request.form.get("price", 0) or 0))
                quantity = max(1, int(request.form.get("quantity", 1) or 1))
                x = float(request.form.get("x", 0) or 0)
                z = float(request.form.get("z", 0) or 0)
                y = float(request.form.get("y", 0) or 0)
            except ValueError:
                flash("Price, quantity and coordinates must be valid numbers.", "warning")
                return redirect(url_for("dayz_shop"))

            item_data = {
                "key": key,
                "display_name": request.form.get("display_name", "").strip(),
                "class_name": request.form.get("class_name", "").strip(),
                "category": request.form.get("category", "General").strip() or "General",
                "description": request.form.get("description", "").strip()[:500],
                "price": price,
                "quantity": quantity,
                "location_name": request.form.get("location_name", "").strip()[:100],
                "x": x,
                "z": z,
                "y": y,
                "allow_custom_location": "allow_custom_location" in request.form,
                "enabled": "enabled" in request.form,
            }

            existing_index = next(
                (
                    index for index, item in enumerate(guild_shop["items"])
                    if str(item.get("key", "")).casefold() == key.casefold()
                ),
                None
            )

            if existing_index is None:
                guild_shop["items"].append(item_data)
                flash("DayZ shop item added.", "success")
            else:
                guild_shop["items"][existing_index].update(item_data)
                flash("DayZ shop item updated.", "success")

        elif action == "delete_item":
            key = request.form.get("key", "")
            guild_shop["items"] = [
                item for item in guild_shop["items"]
                if str(item.get("key", "")) != str(key)
            ]
            flash("DayZ shop item deleted.", "success")

        elif action == "add_vehicle":
            try:
                vx = float(request.form.get("vehicle_x", 0) or 0)
                vz = float(request.form.get("vehicle_z", 0) or 0)
                vy = float(request.form.get("vehicle_y", 0) or 0)
                lifetime = max(1, int(request.form.get("restart_lifetime", 1) or 1))
            except ValueError:
                flash("Vehicle coordinates and restart lifetime must be valid.", "warning")
                return redirect(url_for("dayz_shop"))

            guild_shop["vehicles"].append({
                "id": secrets.token_urlsafe(8),
                "display_name": request.form.get("vehicle_name", "").strip(),
                "class_name": request.form.get("vehicle_class", "").strip(),
                "location_name": request.form.get("vehicle_location_name", "").strip()[:100],
                "x": vx,
                "z": vz,
                "y": vy,
                "restart_lifetime": lifetime,
                "spawned_restart": 0,
                "enabled": True,
            })
            flash("Persistent DayZ vehicle added.", "success")

        elif action == "delete_vehicle":
            vehicle_id = request.form.get("vehicle_id", "")
            guild_shop["vehicles"] = [
                vehicle for vehicle in guild_shop["vehicles"]
                if vehicle.get("id") != vehicle_id
            ]
            flash("DayZ vehicle deleted.", "success")

        with open(shop_path, "w", encoding="utf-8") as file:
            json.dump(root, file, indent=4, ensure_ascii=False)

        return redirect(url_for("dayz_shop"))

    return render_template(
        "dayz/shop.html",
        dayz=settings,
        shop=guild_shop,
        dayz_tab="shop"
    )


@app.route("/integrations/dayz/factions",methods=["GET","POST"])
def dayz_factions():
    gid,s=require_dayz_guild();factions=s.setdefault("factions",[]);roles=bot_api_get(f"/api/guild/{gid}/roles") or []
    if request.method=="POST":
        if request.form.get("action")=="add":factions.append({"id":secrets.token_urlsafe(8),"name":request.form.get("name","").strip(),"leader":request.form.get("leader","").strip(),"members":[x.strip() for x in request.form.get("members","").splitlines() if x.strip()],"role_id":request.form.get("role_id","").strip(),"color":request.form.get("color","991111").replace("#","")})
        elif request.form.get("action")=="delete":s["factions"]=[f for f in factions if f.get("id")!=request.form.get("faction_id","")]
        save_dayz_settings(s);return redirect(url_for("dayz_factions"))
    return render_template("dayz/factions.html",dayz=s,factions=s.get("factions",[]),roles=roles,dayz_tab="factions")

@app.route("/integrations/dayz/map")
def dayz_map():
    gid,s=require_dayz_guild();stats=load_or_create_json(os.path.join(BASE_DIR,"dayz_stats.json"),{"servers":{}});b=load_or_create_json(os.path.join(BASE_DIR,"dayz_bounties.json"),{"guilds":{}});positions=list(stats.get("servers",{}).get(str(gid),{}).get("positions",{}).values());active=[x for x in b.get("guilds",{}).get(str(gid),{}).get("items",[]) if x.get("status")=="active"];return render_template("dayz/map.html",dayz=s,positions=positions,bounties=active,dayz_tab="map")

@app.route("/integrations/dayz/stats")
def dayz_stats_dashboard():
    gid,s=require_dayz_guild();stats=load_or_create_json(os.path.join(BASE_DIR,"dayz_stats.json"),{"servers":{}});players=stats.get("servers",{}).get(str(gid),{}).get("players",{});ranked=sorted(players.items(),key=lambda x:-int(x[1].get("kills",0)));return render_template("dayz/stats.html",dayz=s,players=ranked,dayz_tab="stats")

@app.route("/deadside")
def deadside_legacy_redirect():
    return redirect(url_for("deadside_overview"))


if __name__ == "__main__":
    print("RUNNING FILE:", os.path.abspath(__file__))

    port = int(os.getenv("PORT", "5050"))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        use_reloader=False
    )
