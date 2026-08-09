import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import random
from datetime import datetime, timedelta, timezone
import asyncio
import time
import os
from math import floor
from dotenv import load_dotenv
load_dotenv()
import re
from flask import Flask, jsonify, request
from threading import Thread
from discord.ext import tasks
import secrets
import urllib.request
import urllib.error
import ftplib
import fnmatch
import hashlib
import io
import posixpath

app = Flask(__name__)
print("BOT.PY IS RUNNING")
DASHBOARD_API_KEY = os.getenv("DASHBOARD_API_KEY", "")


def dashboard_authorized():
    supplied_key = request.headers.get("X-Dashboard-Key", "")
    return bool(DASHBOARD_API_KEY and supplied_key == DASHBOARD_API_KEY)


@app.route("/")
def home():
    return "Bot is running!"


@app.route("/api/bot-status")
def bot_status():
    if not dashboard_authorized():
        return jsonify({"error": "Unauthorized"}), 401

    if not bot.is_ready():
        return jsonify({
            "online": False,
            "bot_name": "Starting...",
            "servers": 0,
            "members": 0,
            "latency_ms": 0
        })

    member_count = sum(guild.member_count or 0 for guild in bot.guilds)

    return jsonify({
        "online": True,
        "bot_name": str(bot.user),
        "bot_id": str(bot.user.id),
        "servers": len(bot.guilds),
        "members": member_count,
        "latency_ms": round(bot.latency * 1000)
    })


@app.route("/api/commands")
def bot_commands():
    if not dashboard_authorized():
        return jsonify({"error": "Unauthorized"}), 401

    prefix_commands = [
        {
            "name": command.qualified_name,
            "description": command.help or "No description",
            "type": "prefix"
        }
        for command in bot.walk_commands()
        if not command.hidden
    ]

    slash_commands = []
    for command in bot.tree.get_commands():
        slash_commands.append({
            "name": command.name,
            "description": getattr(command, "description", "No description") or "No description",
            "type": "slash"
        })

    return jsonify({
        "prefix_commands": prefix_commands,
        "slash_commands": slash_commands,
        "total": len(prefix_commands) + len(slash_commands)
    })
@app.route("/api/guilds")
def api_guilds():

    if not dashboard_authorized():
        return jsonify({"error": "Unauthorized"}), 401

    return jsonify([
        {
            "id": str(guild.id),
            "name": guild.name
        }
        for guild in bot.guilds
    ])


@app.route("/api/guild/<int:guild_id>/channels")
def api_channels(guild_id):

    if not dashboard_authorized():
        return jsonify({"error": "Unauthorized"}), 401

    guild = bot.get_guild(guild_id)

    if guild is None:
        return jsonify({"error": "Guild not found"}), 404

    channels = [
        {
            "id": str(channel.id),
            "name": channel.name,
            "type": str(channel.type)
        }
        for channel in guild.channels
    ]

    return jsonify(channels)


@app.route("/api/guild/<int:guild_id>/roles")
def api_roles(guild_id):

    if not dashboard_authorized():
        return jsonify({"error": "Unauthorized"}), 401

    guild = bot.get_guild(guild_id)

    if guild is None:
        return jsonify({"error": "Guild not found"}), 404

    roles = [
        {
            "id": str(role.id),
            "name": role.name
        }
        for role in guild.roles
        if not role.is_default()
    ]

    return jsonify(roles)

async def change_member_role(
    guild_id,
    member_id,
    role_id,
    action
):
    guild = bot.get_guild(
        int(guild_id)
    )

    if guild is None:
        raise ValueError(
            "Guild not found"
        )

    member = guild.get_member(
        int(member_id)
    )

    if member is None:
        try:
            member = await guild.fetch_member(
                int(member_id)
            )
        except discord.NotFound:
            raise ValueError(
                "Member not found"
            )

    role = guild.get_role(
        int(role_id)
    )

    if role is None:
        raise ValueError(
            "Role not found"
        )

    bot_member = guild.me

    if bot_member is None:
        raise ValueError(
            "Bot member not found"
        )

    if role.is_default():
        raise ValueError(
            "The @everyone role cannot be changed"
        )

    if role >= bot_member.top_role:
        raise ValueError(
            "Move the bot role above the selected role"
        )

    if action == "add":
        if role not in member.roles:
            await member.add_roles(
                role,
                reason="Role Manager dashboard"
            )

        message = (
            f"Added {role.name} to "
            f"{member.display_name}"
        )

    elif action == "remove":
        if role in member.roles:
            await member.remove_roles(
                role,
                reason="Role Manager dashboard"
            )

        message = (
            f"Removed {role.name} from "
            f"{member.display_name}"
        )

    else:
        raise ValueError(
            "Invalid role action"
        )

    return {
        "ok": True,
        "message": message,
        "member_id": str(member.id),
        "role_id": str(role.id),
        "action": action
    }
    
@app.route(
    "/api/guild/<int:guild_id>/members"
)

def api_members(guild_id):
    if not dashboard_authorized():
        return jsonify(
            {
                "error": "Unauthorized"
            }
        ), 401

    guild = bot.get_guild(
        guild_id
    )

    if guild is None:
        return jsonify(
            {
                "error": "Guild not found"
            }
        ), 404

    members = []

    for member in guild.members:
        members.append({
            "id": str(member.id),
            "name": member.display_name,
            "username": str(member),
            "avatar_url": str(
                member.display_avatar.url
            ),
            "bot": member.bot,
            "role_ids": [
                str(role.id)
                for role in member.roles
                if not role.is_default()
            ]
        })

    return jsonify(
        members
    )

@app.route("/api/guild/<int:guild_id>/categories")
def api_categories(guild_id):

    if not dashboard_authorized():
        return jsonify({"error": "Unauthorized"}), 401

    guild = bot.get_guild(guild_id)

    if guild is None:
        return jsonify({"error": "Guild not found"}), 404

    categories = [
        {
            "id": str(category.id),
            "name": category.name
        }
        for category in guild.categories
    ]

    return jsonify(categories)
@app.route(
    "/api/guild/<int:guild_id>/member-role",
    methods=["POST"]
)
def api_member_role(guild_id):
    if not dashboard_authorized():
        return jsonify(
            {
                "error": "Unauthorized"
            }
        ), 401

    if not bot.is_ready():
        return jsonify(
            {
                "error": "Bot is not ready"
            }
        ), 503

    payload = request.get_json(
        silent=True
    ) or {}

    member_id = payload.get(
        "member_id"
    )

    role_id = payload.get(
        "role_id"
    )

    action = str(
        payload.get(
            "action",
            ""
        )
    ).strip().lower()

    if not member_id or not role_id:
        return jsonify(
            {
                "error": "Member ID and role ID are required"
            }
        ), 400

    if action not in {
        "add",
        "remove"
    }:
        return jsonify(
            {
                "error": "Invalid action"
            }
        ), 400

    future = asyncio.run_coroutine_threadsafe(
        change_member_role(
            guild_id=guild_id,
            member_id=member_id,
            role_id=role_id,
            action=action
        ),
        bot.loop
    )

    try:
        result = future.result(
            timeout=15
        )

        return jsonify(
            result
        )

    except Exception as error:
        return jsonify(
            {
                "error": str(error)
            }
        ), 500



async def _publish_deadside_faction_embed(guild_id, faction_id):
    root = _read_config(DEADSIDE_FILE, {"servers": {}})
    settings = root.get("servers", {}).get(str(guild_id), {})
    factions = settings.get("factions", [])

    faction = next(
        (
            item
            for item in factions
            if str(item.get("id")) == str(faction_id)
        ),
        None
    )
    if faction is None:
        raise ValueError("Faction not found")

    channel_id = str(faction.get("channel_id", "")).strip()
    if not channel_id.isdigit():
        raise ValueError("Choose a faction details channel first")

    guild = bot.get_guild(int(guild_id))
    if guild is None:
        raise ValueError("Discord server not found")

    channel = guild.get_channel(int(channel_id))
    if channel is None or not hasattr(channel, "send"):
        raise ValueError("Faction details channel not found")

    leader_id = str(faction.get("leader_id", "")).strip()
    member_ids = [str(value) for value in faction.get("member_ids", [])]

    leader = guild.get_member(int(leader_id)) if leader_id.isdigit() else None
    leader_text = leader.mention if leader else "Not selected"

    member_mentions = []
    for member_id in member_ids:
        member = guild.get_member(int(member_id)) if member_id.isdigit() else None
        member_mentions.append(member.mention if member else f"<@{member_id}>")

    role_id = str(faction.get("role_id", "")).strip()
    role = guild.get_role(int(role_id)) if role_id.isdigit() else None
    role_text = role.mention if role else "Not linked"

    try:
        colour = int(str(faction.get("color", "991111")).replace("#", ""), 16)
    except ValueError:
        colour = 0x991111

    embed = discord.Embed(
        title=f"🏴 {faction.get('name', 'Deadside Faction')}",
        description=(
            str(faction.get("description", "")).strip()
            or "Deadside faction details"
        ),
        colour=colour
    )
    embed.add_field(name="Faction Leader", value=leader_text, inline=False)
    embed.add_field(
        name=f"Faction Members ({len(member_mentions)})",
        value="\n".join(member_mentions) if member_mentions else "No members selected",
        inline=False
    )
    embed.add_field(name="Faction Role", value=role_text, inline=False)
    embed.set_footer(text="Pirates Bot • Deadside Factions")

    custom_flag_url = str(faction.get("custom_flag_url", "")).strip()
    if custom_flag_url:
        embed.set_thumbnail(url=custom_flag_url)

    message = None
    message_id = str(faction.get("message_id", "")).strip()
    if message_id.isdigit():
        try:
            message = await channel.fetch_message(int(message_id))
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            message = None

    if message is None:
        message = await channel.send(embed=embed)
    else:
        await message.edit(embed=embed)

    faction["message_id"] = str(message.id)
    faction["channel_id"] = str(channel.id)

    temporary_file = f"{DEADSIDE_FILE}.tmp"
    with open(temporary_file, "w", encoding="utf-8") as file:
        json.dump(root, file, indent=4, ensure_ascii=False)
    os.replace(temporary_file, DEADSIDE_FILE)

    return {
        "ok": True,
        "message": f"Faction embed published in #{channel.name}",
        "channel_id": str(channel.id),
        "message_id": str(message.id),
    }


@app.route(
    "/api/deadside/faction/<int:guild_id>/<faction_id>/publish",
    methods=["POST"]
)
def api_publish_deadside_faction(guild_id, faction_id):
    if not dashboard_authorized():
        return jsonify({"ok": False, "error": "Unauthorized"}), 401

    if not bot.is_ready():
        return jsonify({"ok": False, "error": "Bot is not ready"}), 503

    future = asyncio.run_coroutine_threadsafe(
        _publish_deadside_faction_embed(guild_id, faction_id),
        bot.loop
    )
    try:
        result = future.result(timeout=20)
        return jsonify(result)
    except Exception as error:
        print(f"Faction publish error: {error}")
        return jsonify({"ok": False, "error": str(error)}), 500



@app.route("/api/dashboard/apply/<feature>", methods=["POST"])
def dashboard_apply_feature(feature):
    if not dashboard_authorized():
        return jsonify({"error": "Unauthorized"}), 401

    allowed = {
        "welcome", "tickets", "moderation", "embeds",
        "reaction_roles", "rules", "settings", "economy",
        "polls", "giveaways", "deadside", "dayz"
    }
    if feature not in allowed:
        return jsonify({"error": "Unknown feature"}), 404

    if not bot.is_ready():
        return jsonify({"error": "Bot is not ready"}), 503

    future = asyncio.run_coroutine_threadsafe(
        apply_dashboard_feature(feature),
        bot.loop
    )
    try:
        result = future.result(timeout=15)
        return jsonify({"ok": True, **(result or {})})
    except Exception as error:
        print(f"Dashboard apply error ({feature}): {error}")
        return jsonify({"error": str(error)}), 500


def run_web():
    port = int(
        os.getenv(
            "PORT",
            "10000"
        )
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        use_reloader=False
    )


print("BOT FILE STARTED")
# ------------------- Bot Setup -------------------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

TICKET_CATEGORY_NAME = "Tickets"
STAFF_ROLES = ["Admin", "Staff"]
DAILY_REWARD = 500

# ------------------- DYNAMIC RULES SYSTEM -------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RULES_FILE = os.path.join(BASE_DIR, "rules.json")
WELCOME_FILE = os.path.join(BASE_DIR, "welcome.json")
TICKET_FILE = os.path.join(BASE_DIR, "ticket.json")
MODERATION_FILE = os.path.join(BASE_DIR, "moderation.json")
COMMAND_PERMISSIONS_FILE = os.path.join(BASE_DIR, "command_permissions.json")
EMBED_FILE = os.path.join(BASE_DIR, "embeds.json")
REACTION_ROLE_FILE = os.path.join(BASE_DIR, "reaction_roles.json")
DASHBOARD_FILE = os.path.join(BASE_DIR, "dashboard.json")
ECONOMY_FILE = os.path.join(BASE_DIR, "economy.json")
POLL_FILE = os.path.join(BASE_DIR, "polls.json")
GIVEAWAY_FILE = os.path.join(BASE_DIR, "giveaways.json")
JOBS_CONFIG_FILE = os.path.join(BASE_DIR, "jobs_config.json")
JOBS_USERS_FILE = os.path.join(BASE_DIR, "jobs_users.json")
STICKY_FILE = os.path.join(BASE_DIR, "sticky_messages.json")
ANNOUNCEMENTS_FILE = os.path.join(BASE_DIR, "auto_announcements.json")
REMINDERS_FILE = os.path.join(BASE_DIR, "reminders.json")
ROLE_MANAGER_FILE = os.path.join(BASE_DIR, "role_manager.json")
LOGS_FILE = os.path.join(BASE_DIR, "logs.json")
PERMISSIONS_FILE = os.path.join(BASE_DIR, "permission_manager.json")
DEADSIDE_FILE = os.path.join(BASE_DIR, "deadside.json")
DEADSIDE_STATE_FILE = os.path.join(BASE_DIR, "deadside_state.json")
DEADSIDE_STATS_FILE = os.path.join(BASE_DIR, "deadside_stats.json")
DEADSIDE_PLAYERS_FILE = os.path.join(BASE_DIR, "deadside_players.json")
DEADSIDE_BOUNTIES_FILE = os.path.join(BASE_DIR, "deadside_bounties.json")
DEADSIDE_SESSIONS_FILE = os.path.join(BASE_DIR, "deadside_sessions.json")
DAYZ_FILE = os.path.join(BASE_DIR, "dayz.json")
DAYZ_STATE_FILE = os.path.join(BASE_DIR, "dayz_state.json")
DAYZ_STATS_FILE = os.path.join(BASE_DIR, "dayz_stats.json")
DAYZ_PLAYERS_FILE = os.path.join(BASE_DIR, "dayz_players.json")
DAYZ_BOUNTIES_FILE = os.path.join(BASE_DIR, "dayz_bounties.json")
DAYZ_SHOP_FILE = os.path.join(BASE_DIR, "dayz_shop.json")
DAYZ_SPAWN_QUEUE_FILE = os.path.join(BASE_DIR, "dayz_spawn_queue.json")
TRANSCRIPTS_FOLDER = os.path.join(BASE_DIR, "ticket_transcripts")
os.makedirs(TRANSCRIPTS_FOLDER, exist_ok=True)


# ------------------- DASHBOARD COMMUNICATION -------------------
FEATURE_FILES = {
    "welcome": WELCOME_FILE,
    "tickets": TICKET_FILE,
    "moderation": MODERATION_FILE,
    "embeds": EMBED_FILE,
    "reaction_roles": REACTION_ROLE_FILE,
    "rules": RULES_FILE,
    "settings": DASHBOARD_FILE,
    "economy": ECONOMY_FILE,
    "polls": POLL_FILE,
    "giveaways": GIVEAWAY_FILE,
    "deadside": DEADSIDE_FILE,
    "dayz": DAYZ_FILE,
}


@app.route("/api/dashboard/settings/deadside/<guild_id>", methods=["GET"])
def dashboard_get_deadside_settings(guild_id):
    if not dashboard_authorized():
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    data = _read_config(DEADSIDE_FILE, {"servers": {}})
    settings = dict(data.get("servers", {}).get(str(guild_id), {}) or {})
    settings["password_configured"] = bool(settings.get("password"))
    settings.pop("password", None)
    return jsonify({"ok": True, "settings": settings})


@app.route("/api/dashboard/settings/dayz/<guild_id>", methods=["GET"])
def dashboard_get_dayz_settings(guild_id):
    if not dashboard_authorized():
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    data = _read_config(DAYZ_FILE, {"servers": {}})
    settings = dict(data.get("servers", {}).get(str(guild_id), {}) or {})
    settings["api_token_configured"] = bool(settings.get("nitrado_api_token"))
    settings["ftp_password_configured"] = bool(settings.get("ftp_password"))
    settings.pop("nitrado_api_token", None)
    settings.pop("ftp_password", None)
    return jsonify({"ok": True, "settings": settings})


@app.route("/api/dashboard/settings/<feature>", methods=["POST"])
def dashboard_save_feature(feature):
    """Receive dashboard settings and persist them in the bot service."""
    if not dashboard_authorized():
        return jsonify({"ok": False, "error": "Unauthorized"}), 401

    target_file = FEATURE_FILES.get(feature)
    if target_file is None:
        return jsonify({"ok": False, "error": "Unknown feature"}), 404

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({
            "ok": False,
            "error": "The request body must be a JSON object"
        }), 400

    if feature == "deadside":
        guild_id = str(payload.get("guild_id", "")).strip()
        if not guild_id.isdigit():
            return jsonify({"ok": False, "error": "A valid guild_id is required"}), 400
        root = _read_config(DEADSIDE_FILE, {"servers": {}})
        servers = root.setdefault("servers", {})
        existing = servers.get(guild_id, {}) if isinstance(servers.get(guild_id), dict) else {}
        submitted_password = str(payload.get("password", ""))
        if not submitted_password and existing.get("password"):
            payload["password"] = existing["password"]
        payload.pop("password_configured", None)
        servers[guild_id] = payload
        payload = root

    if feature == "dayz":
        guild_id = str(payload.get("guild_id", "")).strip()
        if not guild_id.isdigit():
            return jsonify({"ok": False, "error": "A valid guild_id is required"}), 400
        root = _read_config(DAYZ_FILE, {"servers": {}})
        servers = root.setdefault("servers", {})
        existing = servers.get(guild_id, {}) if isinstance(servers.get(guild_id), dict) else {}
        if not str(payload.get("nitrado_api_token", "")) and existing.get("nitrado_api_token"):
            payload["nitrado_api_token"] = existing["nitrado_api_token"]
        if not str(payload.get("ftp_password", "")) and existing.get("ftp_password"):
            payload["ftp_password"] = existing["ftp_password"]
        payload.pop("api_token_configured", None)
        payload.pop("ftp_password_configured", None)
        servers[guild_id] = payload
        payload = root

    try:
        temporary_file = f"{target_file}.tmp"
        with open(temporary_file, "w", encoding="utf-8") as file:
            json.dump(payload, file, indent=4, ensure_ascii=False)
        os.replace(temporary_file, target_file)
    except OSError as error:
        print(f"Dashboard save error ({feature}): {error}")
        return jsonify({"ok": False, "error": str(error)}), 500

    return jsonify({
        "ok": True,
        "feature": feature,
        "message": f"{feature} settings saved by the bot service"
    })
def load_rules() -> dict:
    try:
        with open(RULES_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        return {"menu": {}, "sections": {}}
    except json.JSONDecodeError as error:
        print(f"rules.json is invalid: {error}")
        return {"menu": {}, "sections": {}}


def parse_colour(value: str, default: int = 0x991111) -> int:
    try:
        return int(str(value).replace("#", ""), 16)
    except (TypeError, ValueError):
        return default


class RuleSectionButton(discord.ui.Button):
    def __init__(self, section_key: str, section: dict, row: int):
        super().__init__(
            label=section.get("button_label", section_key.replace("_", " ").title()),
            emoji=section.get("button_emoji") or None,
            style=discord.ButtonStyle.danger,
            custom_id=f"pirates_rules:{section_key}",
            row=row
        )
        self.section_key = section_key

    async def callback(self, interaction: discord.Interaction):
        section = load_rules().get("sections", {}).get(self.section_key)
        if section is None:
            await interaction.response.send_message(
                "❌ This rules section no longer exists.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title=section.get("title", self.section_key.replace("_", " ").title()),
            description=section.get("description", "No rules have been added to this section."),
            colour=parse_colour(section.get("color", "991111"))
        )

        thumbnail_url = str(section.get("thumbnail_url", "")).strip()
        image_url = str(section.get("image_url", "")).strip()
        footer = str(section.get("footer", "🏴‍☠️ Pirates Bot Rules")).strip()

        if thumbnail_url:
            embed.set_thumbnail(url=thumbnail_url)
        if image_url:
            embed.set_image(url=image_url)
        if footer:
            embed.set_footer(text=footer)

        await interaction.response.send_message(embed=embed, ephemeral=True)


class RulesMenuView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        sections = load_rules().get("sections", {})

        for index, (section_key, section) in enumerate(sections.items()):
            row = index // 5
            if row > 4:
                break
            self.add_item(RuleSectionButton(section_key, section, row))


@bot.command(name="rulesmenu")
@commands.has_permissions(administrator=True)
async def rules_menu(ctx: commands.Context):
    rules_data = load_rules()
    menu = rules_data.get("menu", {})
    sections = rules_data.get("sections", {})

    if not sections:
        await ctx.send("❌ No rules sections exist. Add one in the dashboard first.")
        return

    embed = discord.Embed(
        title=menu.get("title", "🏴‍☠️ Pirates Server Rules"),
        description=menu.get("description", "Choose a rules section below."),
        colour=parse_colour(menu.get("color", "991111"))
    )

    thumbnail_url = str(menu.get("thumbnail_url", "")).strip()
    image_url = str(menu.get("image_url", "")).strip()
    footer = str(menu.get("footer", "")).strip()

    if thumbnail_url:
        embed.set_thumbnail(url=thumbnail_url)
    if image_url:
        embed.set_image(url=image_url)
    if footer:
        embed.set_footer(text=footer)

    target_channel = ctx.channel
    channel_id = str(menu.get("channel_id", "")).strip()

    if channel_id:
        try:
            target_channel = ctx.guild.get_channel(int(channel_id))
        except ValueError:
            await ctx.send("❌ The rules channel ID is invalid.")
            return

        if target_channel is None:
            await ctx.send("❌ I could not find the selected rules channel.")
            return

    message = await target_channel.send(embed=embed, view=RulesMenuView())
    menu["message_id"] = str(message.id)

    with open(RULES_FILE, "w", encoding="utf-8") as file:
        json.dump(rules_data, file, indent=4, ensure_ascii=False)

    if target_channel.id != ctx.channel.id:
        await ctx.send(f"✅ Rules menu posted in {target_channel.mention}.")


@rules_menu.error
async def rules_menu_error(ctx: commands.Context, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Only administrators can post the rules menu.")
        return
    raise error
# ------------------- GIVEAWAY VIEW -------------------
class GiveawayView(discord.ui.View):
    def __init__(self, duration: int, prize: str, author=None, winner_count: int = 1):
        super().__init__(timeout=duration)
        self.entries = []
        self.prize = prize
        self.author = author
        self.winner_count = max(1, int(winner_count))
        self.message = None

    @discord.ui.button(
        label="Enter Giveaway 🎉",
        style=discord.ButtonStyle.green,
        custom_id="pirates:giveaway_enter"
    )
    async def enter(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in self.entries:
            await interaction.response.send_message("❌ You already entered!", ephemeral=True)
        else:
            self.entries.append(interaction.user.id)
            await interaction.response.send_message("✅ You entered the giveaway!", ephemeral=True)

    async def on_timeout(self):
        if not self.message:
            return
        if not self.entries:
            await self.message.edit(content=f"🎉 Giveaway for **{self.prize}** ended! No entries 😢", view=None)
            return
        selected_ids = random.sample(
            self.entries,
            k=min(self.winner_count, len(self.entries))
        )
        winner_mentions = []
        winners = []
        for winner_id in selected_ids:
            winner = self.message.guild.get_member(winner_id)
            winners.append(winner)
            winner_mentions.append(winner.mention if winner else f"<@{winner_id}>")

        await self.message.edit(
            content=(
                f"🎉 Giveaway for **{self.prize}** ended! "
                f"Winner{'s' if len(winner_mentions) != 1 else ''}: "
                + ", ".join(winner_mentions)
            ),
            view=None
        )
        for winner in winners:
            if winner:
                try:
                    await winner.send(
                        f"🎉 Congrats! You won the giveaway for **{self.prize}** "
                        f"in {self.message.guild.name}!"
                    )
                except discord.HTTPException:
                    pass
  
 # ------------------- POLL -------------------
class PollView(discord.ui.View):
    def __init__(self, question):
        super().__init__(timeout=None)  # Never timeout unless you want
        self.question = question
        self.votes = {"yes": [], "no": []}  # Track user IDs

    async def update_message(self, interaction: discord.Interaction):
        yes_count = len(self.votes["yes"])
        no_count = len(self.votes["no"])
        embed = discord.Embed(
            title="📊 Poll",
            description=f"**{self.question}**",
            color=discord.Color.blurple()
        )
        embed.add_field(name="✅ Yes", value=str(yes_count), inline=True)
        embed.add_field(name="❌ No", value=str(no_count), inline=True)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="✅ Yes", style=discord.ButtonStyle.green, custom_id="pirates:poll_yes")
    async def yes_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in self.votes["yes"]:
            return await interaction.response.send_message("You already voted ✅", ephemeral=True)
        if interaction.user.id in self.votes["no"]:
            self.votes["no"].remove(interaction.user.id)
        self.votes["yes"].append(interaction.user.id)
        await self.update_message(interaction)

    @discord.ui.button(label="❌ No", style=discord.ButtonStyle.red, custom_id="pirates:poll_no")
    async def no_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in self.votes["no"]:
            return await interaction.response.send_message("You already voted ❌", ephemeral=True)
        if interaction.user.id in self.votes["yes"]:
            self.votes["yes"].remove(interaction.user.id)
        self.votes["no"].append(interaction.user.id)
        await self.update_message(interaction)

#Slash command
@tree.command(name="poll", description="Create a simple yes/no poll")
@app_commands.describe(question="Your poll question")
async def poll(interaction: discord.Interaction, question: str):
    view = PollView(question)
    embed = discord.Embed(
        title="📊 Poll",
        description=f"**{question}**",
        color=discord.Color.blurple()
    )
    embed.add_field(name="✅ Yes", value="0", inline=True)
    embed.add_field(name="❌ No", value="0", inline=True)
    await interaction.response.send_message(embed=embed, view=view)

# ------------------- 8 ball -------------------
# 8-ball answers
EIGHT_BALL_ANSWERS = [
    "Yes ✅", "No ❌", "Maybe 🤔", "Definitely 😎", 
    "Absolutely not 🙅‍♂️", "Ask again later ⏳", "It is certain ✔️", "Very doubtful 😬"
]

# /8ball with GIF animation
@tree.command(name="8ball", description="Ask the magic 8-ball a question")
@app_commands.describe(question="Your question for the 8-ball")
async def eight_ball(interaction: discord.Interaction, question: str):
    await interaction.response.defer()  # Let Discord know we're thinking

    # GIF URL for 8-ball shaking
    shake_gif_url = "https://media.giphy.com/media/3o6ZsXjFZqROc7t3xy/giphy.gif"  # Replace with a cool 8-ball GIF if you want

    # Send the initial embed with the shaking GIF
    embed = discord.Embed(
        title="🎱 Magic 8-Ball",
        description="Shaking the 8-ball...",
        color=discord.Color.blue()
    )
    embed.set_image(url=shake_gif_url)
    msg = await interaction.followup.send(embed=embed)

    # Wait a few seconds to simulate shaking
    await asyncio.sleep(3)

    # Pick a random answer
    answer = random.choice(EIGHT_BALL_ANSWERS)

    # Edit the embed to reveal the answer
    result_embed = discord.Embed(
        title="🎱 Magic 8-Ball",
        description=f"**Question:** {question}\n**Answer:** {answer}",
        color=discord.Color.green()
    )
    result_embed.set_thumbnail(url="https://upload.wikimedia.org/wikipedia/commons/8/8b/Magic_eight_ball.png")
    await msg.edit(embed=result_embed)
    
    # ------------------- PIRATE JACK SPARROW -------------------
@tree.command(name="pirate", description="Show a picture of Captain Jack Sparrow 🏴‍☠️")
async def pirate(interaction: discord.Interaction):
    # Example image URL (Jack Sparrow)
    image_url = "https://th.bing.com/th/id/OIP.FtCQVH4TWNF5EpU3XykJNQHaFj?w=205&h=180&c=7&r=0&o=7&pid=1.7&rm=3"

    embed = discord.Embed(
        title="🏴‍☠️ Captain Jack Sparrow",
        description="Savvy?",
        color=discord.Color.gold()
    )
    embed.set_image(url=image_url)

    await interaction.response.send_message(embed=embed)

# ------------------- GIVEAWAY SLASH COMMAND -------------------
@tree.command(name="giveaway", description="Start a giveaway")
@app_commands.describe(duration="Duration in seconds", prize="Prize for the giveaway")
@app_commands.checks.has_permissions(administrator=True)
async def giveaway(interaction: discord.Interaction, duration: int, prize: str):
    view = GiveawayView(duration, prize, interaction.user)
    await interaction.response.send_message(
        f"🎉 **GIVEAWAY STARTED** 🎉\nPrize: **{prize}**\nEnds in {duration} seconds!\nClick below to enter!",
        view=view
    )
    view.message = await interaction.original_response()
    
    # ------------------- EMBED COMMAND -------------------
@tree.command(name="embed", description="Create a custom embed message")
@app_commands.describe(
    title="Title of the embed",
    description="Description/content of the embed",
    color="Hex color code (optional, e.g., #FF0000)"
)
async def embed(interaction: discord.Interaction, title: str, description: str, color: str = "#00FF00"):
    # Check if the user has permission to manage messages (optional)
    if not interaction.user.guild_permissions.manage_messages:
        return await interaction.response.send_message("❌ You need Manage Messages permission to use this.", ephemeral=True)
    
    # Convert hex color string to Discord color
    try:
        color_value = int(color.strip("#"), 16)
        embed_color = discord.Color(color_value)
    except:
        embed_color = discord.Color.green()

    embed = discord.Embed(
        title=title,
        description=description,
        color=embed_color
    )
    
    await interaction.response.send_message(embed=embed)



# ------------------- STAFF CHECK (ADDED) -------------------
def is_staff():
    async def predicate(interaction: discord.Interaction):
        if interaction.user.guild_permissions.administrator:
            return True
        user_roles = [role.name for role in interaction.user.roles]
        return any(r in STAFF_ROLES for r in user_roles)
    return app_commands.check(predicate)

# ------------------- JSON HELPERS -------------------
def load_json(file, default):
    try:
        with open(file, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return default

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=4)

def get_bank():
    return load_json("bank.json", {})

def update_bank(user_id, change=0, bank=False):
    users = get_bank()
    uid = str(user_id)
    users.setdefault(uid, {"wallet": 0, "bank": 0, "last_daily": None})
    key = "bank" if bank else "wallet"
    users[uid][key] += change
    save_json("bank.json", users)

def get_welcome_settings():
    return load_json("welcome.json", {})

def update_welcome_settings(data):
    save_json("welcome.json", data)

def get_reaction_roles():
    return load_json("reaction_roles.json", {})

def update_reaction_roles(data):
    save_json("reaction_roles.json", data)
    
def get_command_access(
guild_id,
command_name
):
    data = load_json(
        COMMAND_PERMISSIONS_FILE,
        {
            "guilds": {}
        }
    )

    guild_settings = (
        data.get("guilds", {})
        .get(str(guild_id), {})
    )

    commands_data = guild_settings.get(
        "commands",
        {}
    )

    return commands_data.get(
        str(command_name).lower(),
        "everyone"
    )


def member_is_command_staff(member):
    if member is None:
        return False

    if member.guild_permissions.administrator:
        return True

    member_role_names = {
        role.name.lower()
        for role in member.roles
    }

    return any(
        role_name.lower() in member_role_names
        for role_name in STAFF_ROLES
    )
# =========================================================
# LOGGING ENGINE
# =========================================================

MAX_LOGS_PER_GUILD = 5000


def save_guild_log(
    guild_id,
    log_type,
    data
):
    logs_data = load_json(
        LOGS_FILE,
        {
            "guilds": {}
        }
    )

    if not isinstance(logs_data, dict):
        logs_data = {
            "guilds": {}
        }

    guilds = logs_data.setdefault(
        "guilds",
        {}
    )

    guild_logs = guilds.setdefault(
        str(guild_id),
        []
    )

    if not isinstance(guild_logs, list):
        guild_logs = []
        guilds[str(guild_id)] = guild_logs

    entry = {
        "id": secrets.token_hex(8),
        "type": str(log_type),
        "timestamp": time.time(),
        "data": data
    }

    guild_logs.append(
        entry
    )

    if len(guild_logs) > MAX_LOGS_PER_GUILD:
        guilds[str(guild_id)] = guild_logs[
            -MAX_LOGS_PER_GUILD:
        ]

    save_json(
        LOGS_FILE,
        logs_data
    )   
    # =========================================================
# MESSAGE LOG EVENTS
# =========================================================

@bot.event
async def on_message_delete(
    message: discord.Message
):
    if not message.guild:
        return

    if message.author.bot:
        return

    attachments = [
        attachment.url
        for attachment in message.attachments
    ]

    save_guild_log(
        message.guild.id,
        "message_delete",
        {
            "user_id": str(message.author.id),
            "user_name": str(message.author),
            "display_name": message.author.display_name,
            "channel_id": str(message.channel.id),
            "channel_name": getattr(
                message.channel,
                "name",
                "Unknown"
            ),
            "message": message.content[:2000],
            "attachments": attachments,
            "message_id": str(message.id)
        }
    )


@bot.event
async def on_message_edit(
    before: discord.Message,
    after: discord.Message
):
    if not before.guild:
        return

    if before.author.bot:
        return

    if before.content == after.content:
        return

    save_guild_log(
        before.guild.id,
        "message_edit",
        {
            "user_id": str(before.author.id),
            "user_name": str(before.author),
            "display_name": before.author.display_name,
            "channel_id": str(before.channel.id),
            "channel_name": getattr(
                before.channel,
                "name",
                "Unknown"
            ),
            "before": before.content[:2000],
            "after": after.content[:2000],
            "message_id": str(before.id),
            "jump_url": after.jump_url
        }
    )
    # =========================================================
# MEMBER JOIN / LEAVE LOGS
# =========================================================

@bot.event
async def on_member_join(member: discord.Member):
    save_guild_log(
        member.guild.id,
        "member_join",
        {
            "user_id": str(member.id),
            "user_name": str(member),
            "display_name": member.display_name,
            "joined_at": (
                member.joined_at.isoformat()
                if member.joined_at
                else None
            ),
            "created_at": (
                member.created_at.isoformat()
            ),
            "bot": member.bot
        }
    )


@bot.event
async def on_member_remove(member: discord.Member):
    save_guild_log(
        member.guild.id,
        "member_leave",
        {
            "user_id": str(member.id),
            "user_name": str(member),
            "display_name": member.display_name,
            "joined_at": (
                member.joined_at.isoformat()
                if member.joined_at
                else None
            ),
            "bot": member.bot
        }
    )
@bot.event
async def on_member_update(
    before: discord.Member,
    after: discord.Member
):
    if before.display_name != after.display_name:
        save_guild_log(
            after.guild.id,
            "nickname_change",
            {
                "user_id": str(after.id),
                "user_name": str(after),
                "before": before.display_name,
                "after": after.display_name
            }
        )
# =========================================================
# PIRATE JOB SYSTEM
# =========================================================

DEFAULT_PIRATE_JOBS = {
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


def load_jobs_config():
    data = load_json(
        JOBS_CONFIG_FILE,
        {
            "guilds": {}
        }
    )

    if not isinstance(data, dict):
        data = {
            "guilds": {}
        }

    data.setdefault("guilds", {})

    return data


def save_jobs_config(data):
    save_json(
        JOBS_CONFIG_FILE,
        data
    )


def get_guild_jobs_config(guild_id):
    data = load_jobs_config()
    guild_id = str(guild_id)

    guild_settings = data["guilds"].setdefault(
        guild_id,
        {
            "enabled": True,
            "daily_cooldown": 86400,
            "xp_min": 20,
            "xp_max": 45,
            "level_pay_bonus": 25,
            "jobs": DEFAULT_PIRATE_JOBS.copy()
        }
    )

    guild_settings.setdefault("enabled", True)
    guild_settings.setdefault("daily_cooldown", 86400)
    guild_settings.setdefault("xp_min", 20)
    guild_settings.setdefault("xp_max", 45)
    guild_settings.setdefault("level_pay_bonus", 25)
    guild_settings.setdefault(
        "jobs",
        DEFAULT_PIRATE_JOBS.copy()
    )

    if not isinstance(guild_settings["jobs"], dict):
        guild_settings["jobs"] = DEFAULT_PIRATE_JOBS.copy()

    save_jobs_config(data)

    return guild_settings


def load_jobs_users():
    data = load_json(
        JOBS_USERS_FILE,
        {
            "guilds": {}
        }
    )

    if not isinstance(data, dict):
        data = {
            "guilds": {}
        }

    data.setdefault("guilds", {})

    return data


def save_jobs_users(data):
    save_json(
        JOBS_USERS_FILE,
        data
    )


def job_level_requirement(level):
    return max(
        100,
        int(level) * 100
    )


def job_progress_bar(current_xp, required_xp):
    if required_xp <= 0:
        return "⬜" * 10

    filled = min(
        10,
        int((current_xp / required_xp) * 10)
    )

    return "🟥" * filled + "⬛" * (10 - filled)


def seconds_until_job_ready(last_worked, cooldown):
    if not last_worked:
        return 0

    try:
        last_timestamp = float(last_worked)
    except (TypeError, ValueError):
        return 0

    elapsed = time.time() - last_timestamp

    return max(
        0,
        int(cooldown - elapsed)
    )


def format_job_cooldown(seconds):
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    parts = []

    if hours:
        parts.append(f"{hours}h")

    if minutes:
        parts.append(f"{minutes}m")

    if seconds or not parts:
        parts.append(f"{seconds}s")

    return " ".join(parts)


# ---------------------------------------------------------
# /jobs
# ---------------------------------------------------------

@tree.command(
    name="jobs",
    description="View the pirate jobs available in this server"
)
async def jobs_command(
    interaction: discord.Interaction
):
    if interaction.guild is None:
        await interaction.response.send_message(
            "❌ This command can only be used in a server.",
            ephemeral=True
        )
        return

    settings = get_guild_jobs_config(
        interaction.guild.id
    )

    if not settings.get("enabled", True):
        await interaction.response.send_message(
            "❌ The pirate jobs system is disabled in this server.",
            ephemeral=True
        )
        return

    available_jobs = [
        (job_key, job)
        for job_key, job in settings.get("jobs", {}).items()
        if job.get("enabled", True)
    ]

    embed = discord.Embed(
        title="🏴‍☠️ Pirate Careers",
        description=(
            "Choose your place aboard the fleet with "
            "`/choosejob`.\n\n"
            "Higher-risk jobs may earn more treasure, "
            "but a failed voyage can cost you gold."
        ),
        colour=discord.Colour.dark_red()
    )

    if not available_jobs:
        embed.description = (
            "No pirate jobs are currently available."
        )

    for job_key, job in available_jobs:
        embed.add_field(
            name=(
                f"{job.get('emoji', '⚓')} "
                f"{job.get('name', job_key.title())}"
            ),
            value=(
                f"{job.get('description', 'No description')}\n"
                f"**Pay:** ${int(job.get('min_pay', 0)):,}"
                f"–${int(job.get('max_pay', 0)):,}\n"
                f"**Risk:** {int(job.get('risk', 0))}%\n"
                f"**Job ID:** `{job_key}`"
            ),
            inline=False
        )

    embed.set_footer(
        text="Pirates Bot • Choose wisely, matey."
    )

    await interaction.response.send_message(
        embed=embed
    )


# ---------------------------------------------------------
# /choosejob
# ---------------------------------------------------------

@tree.command(
    name="choosejob",
    description="Choose your pirate career"
)
@app_commands.describe(
    job="Job ID shown in /jobs"
)
async def choosejob(
    interaction: discord.Interaction,
    job: str
):
    if interaction.guild is None:
        await interaction.response.send_message(
            "❌ This command can only be used in a server.",
            ephemeral=True
        )
        return

    settings = get_guild_jobs_config(
        interaction.guild.id
    )

    if not settings.get("enabled", True):
        await interaction.response.send_message(
            "❌ The pirate jobs system is disabled.",
            ephemeral=True
        )
        return

    job_key = (
        str(job)
        .strip()
        .lower()
        .replace(" ", "_")
    )

    job_data = settings.get(
        "jobs",
        {}
    ).get(job_key)

    if not job_data or not job_data.get("enabled", True):
        await interaction.response.send_message(
            "❌ That pirate job does not exist or is disabled. "
            "Use `/jobs` to see the available jobs.",
            ephemeral=True
        )
        return

    users_data = load_jobs_users()
    guild_users = users_data["guilds"].setdefault(
        str(interaction.guild.id),
        {}
    )

    existing = guild_users.get(
        str(interaction.user.id),
        {}
    )

    guild_users[str(interaction.user.id)] = {
        "job": job_key,
        "level": max(
            1,
            int(existing.get("level", 1))
        ),
        "xp": max(
            0,
            int(existing.get("xp", 0))
        ),
        "total_earned": max(
            0,
            int(existing.get("total_earned", 0))
        ),
        "successful_jobs": max(
            0,
            int(existing.get("successful_jobs", 0))
        ),
        "failed_jobs": max(
            0,
            int(existing.get("failed_jobs", 0))
        ),
        "last_worked": existing.get(
            "last_worked"
        )
    }

    save_jobs_users(users_data)

    embed = discord.Embed(
        title="⚓ New Pirate Career",
        description=(
            f"{interaction.user.mention}, you are now a "
            f"**{job_data.get('name', job_key.title())}**!"
        ),
        colour=discord.Colour.dark_red()
    )

    embed.add_field(
        name="Role",
        value=(
            f"{job_data.get('emoji', '⚓')} "
            f"{job_data.get('name', job_key.title())}"
        ),
        inline=True
    )

    embed.add_field(
        name="Possible pay",
        value=(
            f"${int(job_data.get('min_pay', 0)):,}"
            f"–${int(job_data.get('max_pay', 0)):,}"
        ),
        inline=True
    )

    embed.add_field(
        name="Voyage risk",
        value=f"{int(job_data.get('risk', 0))}%",
        inline=True
    )

    await interaction.response.send_message(
        embed=embed
    )


# ---------------------------------------------------------
# /jobwork
# ---------------------------------------------------------

@tree.command(
    name="jobwork",
    description="Complete a voyage for your pirate job"
)
async def jobwork(
    interaction: discord.Interaction
):
    if interaction.guild is None:
        await interaction.response.send_message(
            "❌ This command can only be used in a server.",
            ephemeral=True
        )
        return

    await interaction.response.defer()

    settings = get_guild_jobs_config(
        interaction.guild.id
    )

    if not settings.get("enabled", True):
        await interaction.followup.send(
            "❌ The pirate jobs system is disabled.",
            ephemeral=True
        )
        return

    users_data = load_jobs_users()
    guild_users = users_data["guilds"].setdefault(
        str(interaction.guild.id),
        {}
    )

    user_id = str(interaction.user.id)
    user_data = guild_users.get(user_id)

    if not user_data:
        await interaction.followup.send(
            "❌ You do not have a pirate job. "
            "Use `/jobs` and `/choosejob` first.",
            ephemeral=True
        )
        return

    job_key = user_data.get("job")
    job_data = settings.get(
        "jobs",
        {}
    ).get(job_key)

    if not job_data or not job_data.get("enabled", True):
        await interaction.followup.send(
            "❌ Your selected job is no longer available.",
            ephemeral=True
        )
        return

    cooldown = max(
        0,
        int(settings.get("daily_cooldown", 86400))
    )

    remaining = seconds_until_job_ready(
        user_data.get("last_worked"),
        cooldown
    )

    if remaining > 0:
        await interaction.followup.send(
            "⏳ Your crew is still recovering from the last voyage. "
            f"Try again in **{format_job_cooldown(remaining)}**.",
            ephemeral=True
        )
        return

    level = max(
        1,
        int(user_data.get("level", 1))
    )

    base_pay = random.randint(
        int(job_data.get("min_pay", 0)),
        int(job_data.get("max_pay", 0))
    )

    level_bonus = (
        level
        * int(settings.get("level_pay_bonus", 25))
    )

    reward = max(
        0,
        base_pay + level_bonus
    )

    risk = max(
        0,
        min(
            100,
            int(job_data.get("risk", 0))
        )
    )

    failed = (
        risk > 0
        and random.randint(1, 100) <= risk
    )

    user_data["last_worked"] = time.time()

    if failed:
        loss = min(
            reward,
            get_bank().get(
                user_id,
                {}
            ).get(
                "wallet",
                0
            )
        )

        if loss > 0:
            update_bank(
                interaction.user.id,
                -loss
            )

        user_data["failed_jobs"] = (
            int(user_data.get("failed_jobs", 0))
            + 1
        )

        embed = discord.Embed(
            title="🌊 Voyage Failed",
            description=(
                f"{interaction.user.mention}, disaster struck "
                f"during your voyage as a "
                f"**{job_data.get('name', job_key.title())}**."
            ),
            colour=discord.Colour.red()
        )

        embed.add_field(
            name="Treasure lost",
            value=f"${loss:,}",
            inline=True
        )

        embed.add_field(
            name="Risk",
            value=f"{risk}%",
            inline=True
        )

    else:
        update_bank(
            interaction.user.id,
            reward
        )

        xp_min = max(
            1,
            int(settings.get("xp_min", 20))
        )

        xp_max = max(
            xp_min,
            int(settings.get("xp_max", 45))
        )

        gained_xp = random.randint(
            xp_min,
            xp_max
        )

        user_data["xp"] = (
            int(user_data.get("xp", 0))
            + gained_xp
        )

        user_data["total_earned"] = (
            int(user_data.get("total_earned", 0))
            + reward
        )

        user_data["successful_jobs"] = (
            int(user_data.get("successful_jobs", 0))
            + 1
        )

        levels_gained = 0

        while (
            user_data["xp"]
            >= job_level_requirement(
                user_data["level"]
            )
        ):
            user_data["xp"] -= job_level_requirement(
                user_data["level"]
            )

            user_data["level"] += 1
            levels_gained += 1

        embed = discord.Embed(
            title="🏴‍☠️ Voyage Complete",
            description=(
                f"{interaction.user.mention} completed a voyage "
                f"as a **{job_data.get('name', job_key.title())}**."
            ),
            colour=discord.Colour.gold()
        )

        embed.add_field(
            name="Treasure earned",
            value=f"${reward:,}",
            inline=True
        )

        embed.add_field(
            name="Experience",
            value=f"+{gained_xp} XP",
            inline=True
        )

        embed.add_field(
            name="Current level",
            value=str(user_data["level"]),
            inline=True
        )

        if levels_gained:
            embed.add_field(
                name="🎉 Promotion",
                value=(
                    f"You gained **{levels_gained}** level"
                    f"{'s' if levels_gained != 1 else ''}!"
                ),
                inline=False
            )

    guild_users[user_id] = user_data
    save_jobs_users(users_data)

    await interaction.followup.send(
        embed=embed
    )


# ---------------------------------------------------------
# /jobinfo
# ---------------------------------------------------------

@tree.command(
    name="jobinfo",
    description="View your pirate career progress"
)
@app_commands.describe(
    user="Member to inspect, or leave blank for yourself"
)
async def jobinfo(
    interaction: discord.Interaction,
    user: discord.Member | None = None
):
    if interaction.guild is None:
        await interaction.response.send_message(
            "❌ This command can only be used in a server.",
            ephemeral=True
        )
        return

    target = user or interaction.user

    settings = get_guild_jobs_config(
        interaction.guild.id
    )

    users_data = load_jobs_users()
    user_data = (
        users_data.get("guilds", {})
        .get(str(interaction.guild.id), {})
        .get(str(target.id))
    )

    if not user_data:
        await interaction.response.send_message(
            f"❌ {target.mention} does not have a pirate job.",
            ephemeral=True
        )
        return

    job_key = user_data.get("job")
    job_data = settings.get(
        "jobs",
        {}
    ).get(
        job_key,
        {
            "name": job_key.title(),
            "emoji": "⚓",
            "min_pay": 0,
            "max_pay": 0,
            "risk": 0
        }
    )

    level = max(
        1,
        int(user_data.get("level", 1))
    )

    current_xp = max(
        0,
        int(user_data.get("xp", 0))
    )

    required_xp = job_level_requirement(
        level
    )

    embed = discord.Embed(
        title="📜 Pirate Career Record",
        description=target.mention,
        colour=discord.Colour.dark_red()
    )

    embed.set_thumbnail(
        url=target.display_avatar.url
    )

    embed.add_field(
        name="Career",
        value=(
            f"{job_data.get('emoji', '⚓')} "
            f"{job_data.get('name', job_key.title())}"
        ),
        inline=True
    )

    embed.add_field(
        name="Level",
        value=str(level),
        inline=True
    )

    embed.add_field(
        name="Risk",
        value=f"{int(job_data.get('risk', 0))}%",
        inline=True
    )

    embed.add_field(
        name="Experience",
        value=(
            f"{current_xp}/{required_xp} XP\n"
            f"{job_progress_bar(current_xp, required_xp)}"
        ),
        inline=False
    )

    embed.add_field(
        name="Total treasure earned",
        value=f"${int(user_data.get('total_earned', 0)):,}",
        inline=True
    )

    embed.add_field(
        name="Successful voyages",
        value=str(
            int(user_data.get("successful_jobs", 0))
        ),
        inline=True
    )

    embed.add_field(
        name="Failed voyages",
        value=str(
            int(user_data.get("failed_jobs", 0))
        ),
        inline=True
    )

    await interaction.response.send_message(
        embed=embed
    )


# ---------------------------------------------------------
# /jobleaderboard
# ---------------------------------------------------------

@tree.command(
    name="jobleaderboard",
    description="View the server's top pirate workers"
)
async def jobleaderboard(
    interaction: discord.Interaction
):
    if interaction.guild is None:
        await interaction.response.send_message(
            "❌ This command can only be used in a server.",
            ephemeral=True
        )
        return

    users_data = load_jobs_users()

    guild_users = (
        users_data.get("guilds", {})
        .get(str(interaction.guild.id), {})
    )

    ranked = sorted(
        guild_users.items(),
        key=lambda item: (
            int(item[1].get("level", 1)),
            int(item[1].get("total_earned", 0))
        ),
        reverse=True
    )[:10]

    embed = discord.Embed(
        title="🏆 Pirate Jobs Leaderboard",
        colour=discord.Colour.gold()
    )

    if not ranked:
        embed.description = (
            "No pirate workers have started a career yet."
        )

    settings = get_guild_jobs_config(
        interaction.guild.id
    )

    for position, (user_id, user_data) in enumerate(
        ranked,
        start=1
    ):
        member = interaction.guild.get_member(
            int(user_id)
        )

        member_name = (
            member.display_name
            if member
            else f"Unknown Pirate ({user_id})"
        )

        job_key = user_data.get(
            "job",
            "unknown"
        )

        job_data = settings.get(
            "jobs",
            {}
        ).get(
            job_key,
            {
                "name": job_key.title(),
                "emoji": "⚓"
            }
        )

        embed.add_field(
            name=f"#{position} — {member_name}",
            value=(
                f"{job_data.get('emoji', '⚓')} "
                f"**{job_data.get('name', job_key.title())}**\n"
                f"Level {int(user_data.get('level', 1))} • "
                f"${int(user_data.get('total_earned', 0)):,} earned"
            ),
            inline=False
        )

    await interaction.response.send_message(
        embed=embed
    )

# ---------- JSON HELPERS ----------
def load_jobs():
    try:
        with open(JOB_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_jobs(data):
    with open(JOB_FILE, "w") as f:
        json.dump(data, f, indent=4)

def load_activity():
    try:
        with open(ACTIVITY_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_activity(data):
    with open(ACTIVITY_FILE, "w") as f:
        json.dump(data, f, indent=4)
        
@bot.check
async def check_prefix_command_permissions(
    ctx
):
    if ctx.guild is None:
        return True

    if ctx.command is None:
        return True

    command_name = (
        ctx.command.qualified_name
        .split(" ")[0]
        .lower()
    )

    access = get_command_access(
        ctx.guild.id,
        command_name
    )

    if access == "disabled":
        await ctx.send(
            "❌ This command is disabled in this server."
        )
        return False

    if access == "staff":
        if not member_is_command_staff(
            ctx.author
        ):
            await ctx.send(
                "❌ This command is restricted to staff."
            )
            return False

    return True


async def check_slash_command_permissions(
    interaction
):
    if interaction.guild is None:
        return True

    command = interaction.command

    if command is None:
        return True

    command_name = str(
        command.name
    ).lower()

    access = get_command_access(
        interaction.guild.id,
        command_name
    )

    if access == "disabled":
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "❌ This command is disabled in this server.",
                ephemeral=True
            )
        return False

    if access == "staff":
        if not member_is_command_staff(
            interaction.user
        ):
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ This command is restricted to staff.",
                    ephemeral=True
                )
            return False

    return True


bot.tree.interaction_check = (
    check_slash_command_permissions
)
    

# ------------------- PIRATE AI HELPER -------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
PIRATE_AI_MODEL = os.getenv("PIRATE_AI_MODEL", "gpt-5-mini").strip() or "gpt-5-mini"
PIRATE_AI_COOLDOWN = max(3, int(os.getenv("PIRATE_AI_COOLDOWN", "8") or 8))
PIRATE_AI_MAX_QUESTION = max(
    100,
    min(int(os.getenv("PIRATE_AI_MAX_QUESTION", "1200") or 1200), 4000)
)

# Optional comma-separated channel IDs. Leave blank to allow the helper anywhere.
PIRATE_AI_CHANNEL_IDS = {
    value.strip()
    for value in os.getenv("PIRATE_AI_CHANNEL_IDS", "").split(",")
    if value.strip().isdigit()
}

_pirate_ai_last_used = {}

PIRATE_BOT_KNOWLEDGE = r"""
You are the Pirates Bot AI Helper inside Discord.

ONLY help with Pirates Bot, the Pirates Bot dashboard, Discord features,
Deadside integration, and DayZ integration.

RULES:
- Keep answers short, practical, and Discord-friendly.
- Use a light pirate style without making the answer hard to read.
- Prefer exact slash-command examples in backticks.
- Never invent a command.
- Never invent balances, stats, coordinates, server state, or configuration.
- Never reveal API keys, tokens, FTP credentials, passwords, or private config.
- If unsure, say you cannot find a matching Pirates Bot command and suggest
  checking the help guide or asking an administrator.
- For dashboard questions, use:
  https://amusing-inspiration-production-eab1.up.railway.app/
- If the user asks something unrelated to Pirates Bot, politely redirect them.

ECONOMY:
- `/balance` shows wallet and bank.
- `/work` earns money.
- `/daily` claims the daily reward.
- `/deposit amount:<amount>` moves wallet money into bank.
- `/withdraw amount:<amount>` moves bank money into wallet.
- `/pay member:@User amount:<amount>` pays another member.
- `/rob member:@User` attempts to rob another member.
- `/leaderboard` shows the richest users.
- `/slots bet:<amount>` plays slots.
- `/blackjack bet:<amount>` plays blackjack.
- `/roulette amount:<amount> choice:<red|black|green|0-36>` plays roulette.

PIRATE JOBS:
- `/jobs` lists jobs.
- `/choosejob job:<job id>` selects a job.
- `/jobwork` works the selected job.
- `/jobinfo` shows job progress.
- `/jobleaderboard` shows top workers.

COMMUNITY:
- `/poll question:<question>` creates a yes/no poll.
- `/8ball question:<question>` asks the 8-ball.
- `/giveaway duration:<seconds> prize:<prize>` starts a giveaway.
- `/embed` creates a custom embed if the user has permission.
- `/remindme minutes:<minutes> message:<message>` creates a reminder.
- `/pirate` posts the pirate picture.

DEADSIDE:
- `/ds link gamertag:<name>` links a Deadside gamertag.
- `/ds unlink` unlinks it.
- `/ds stats` shows tracked Deadside stats.
- `/ds session` shows the current earning session.
- `/ds leaderboard` shows the Deadside kill leaderboard.
- `/ds bounty_create gamertag:<name> amount:<amount>` places a bounty.
- `/ds bounties` lists active Deadside bounties.
- `/dsstats` is a quick stats alias.
- `/session` is a quick session alias.

DAYZ:
- `/dz link gamertag:<name> guid:<optional guid>` links a DayZ player.
- `/dz whereami` shows the latest logged DayZ position.
- `/dz stats` shows DayZ stats.
- `/dz leaderboard` shows the DayZ kill leaderboard.
- `/dz playerlocations` is administrator-only.
- `/dz bounty gamertag:<name> amount:<amount>` places a DayZ bounty.
- `/dz bounties` lists DayZ bounties.
- `/dz buy item_key:<key> quantity:<number>` buys a DayZ shop item.
- `/buy item:<key> quantity:<number>` is the shorter DayZ shop command.
- Custom-location items can also use x, z and y coordinates.

ADMIN:
- `/help setup` posts the help guide and is administrator-only.
- `/force link game:<Deadside|DayZ> member:@User gamertag:<name> guid:<optional>` lets an administrator override/link a player's game account.
- `/roleadd` and `/roleremove` manage roles.
- `/setreactionrole` sets a reaction role.
- `/setwelcome` and `/removewelcome` manage welcome setup where available.
- `/setautorole` and `/removeautorole` manage auto roles.
- `/removeallmsgs` clears messages and is administrator-only.
- Economy admin commands may include `/addmoney`, `/removemoney`,
  `/economywipe`, and `/money` when present in the live command list.



BOT SETUP / TROUBLESHOOTING:
- Pirates Bot dashboard: https://amusing-inspiration-production-eab1.up.railway.app/
- Administrators should sign in with Discord, open Manage Servers, invite Pirates
  Bot if needed, then select the server they want to manage.
- A user must own the server or have Manage Server / Administrator permission
  for Discord to report it as manageable.
- After inviting Pirates Bot, return to Manage Servers and refresh/re-login if
  the server still shows the bot as not installed.
- The bot invite must include both the `bot` and `applications.commands` scopes.
- The bot should have the Discord permissions required by the features being
  used. If channels or roles are missing in selectors, first check that the bot
  can view those channels/roles and that the correct server is selected.
- Dashboard settings are server-specific. Always make sure the correct Discord
  server is selected before changing settings.
- Important Railway environment variable names can include:
  `DISCORD_TOKEN`, `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`,
  `DISCORD_REDIRECT_URI`, `DASHBOARD_API_KEY`, `BOT_API_URL`,
  `FLASK_SECRET_KEY`, `BOT_OWNER_ID`, and `OPENAI_API_KEY`.
- Never ask the user to paste secret values into Discord. Explain where the
  variable belongs, but never reveal or request the actual secret.
- `DASHBOARD_API_KEY` must match between the bot service and dashboard service.
- `BOT_API_URL` on the dashboard service must point at the running bot API
  service address.
- If Railway says a Python file has an error, suggest checking the deployment
  traceback and running `python -m py_compile bot.py` or
  `python -m py_compile dashboard/app.py` locally.
- If a dashboard page returns Internal Server Error, ask for the Railway
  traceback and identify the exact template/route error instead of guessing.
- If slash commands do not appear after a deployment, first confirm the bot
  started successfully and command sync completed.

DEADSIDE SETUP:
- Open the Deadside integration in the dashboard after selecting the correct
  Discord server.
- Configure the server connection values required by that integration.
- Configure Discord destination channels for feeds, logs, radar, factions and
  other enabled systems.
- Deadside gamertags can normally be linked by the user with `/ds link`.
- Administrators can force a link with `/force link game:deadside`.
- Deadside shares the same Pirates Bot economy rather than creating a separate
  wallet.

DAYZ SETUP:
- Open the DayZ integration in the dashboard after selecting the correct server.
- Configure the Nitrado service information and FTPS/admin-log access required
  by the DayZ integration.
- DayZ player-location features depend on position information being available
  in the DayZ admin logs.
- Configure killfeed, deathfeed, radar, economy, shop, factions and other
  features from the DayZ dashboard tabs.
- DayZ gamertags can normally be linked by the user with `/dz link`.
- Administrators can force a link with `/force link game:dayz`.
- DayZ uses the shared Pirates Bot economy.

DASHBOARD:
- Sign in with Discord.
- Select a server the user can manage.
- Pirates Bot must be installed in that server.
- The dashboard controls Welcome, Tickets, Rules, Reaction Roles, Moderation,
  Embeds, Polls, Giveaways, Economy, Jobs, Command Permissions, Deadside,
  DayZ, and other enabled modules.
- Deadside and DayZ use the same Pirates Bot economy.
"""


def _pirate_live_commands():
    """Return the commands actually registered in the running bot."""
    lines = []

    def walk(command, prefix=""):
        name = f"{prefix} {command.name}".strip()
        description = getattr(command, "description", "") or "No description"
        lines.append(f"/{name} — {description}")

        for child in getattr(command, "commands", []) or []:
            walk(child, name)

    try:
        for command in bot.tree.get_commands():
            walk(command)
    except Exception:
        pass

    return "\n".join(lines[:180])


def _pirate_ai_extract_text(payload):
    if not isinstance(payload, dict):
        return ""

    output_text = payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    chunks = []
    for item in payload.get("output", []) or []:
        if not isinstance(item, dict):
            continue

        for content in item.get("content", []) or []:
            if not isinstance(content, dict):
                continue

            text = content.get("text")
            if isinstance(text, str) and text.strip():
                chunks.append(text.strip())

    return "\n".join(chunks).strip()


def _pirate_ai_request(question, command_list):
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    request_body = json.dumps({
        "model": PIRATE_AI_MODEL,
        "store": False,
        "instructions": (
            PIRATE_BOT_KNOWLEDGE
            + "\n\nLIVE SLASH COMMANDS CURRENTLY REGISTERED:\n"
            + (command_list or "No live command list available.")
        ),
        "input": question,
        "max_output_tokens": 350,
    }).encode("utf-8")

    api_request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=request_body,
        method="POST",
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
            "User-Agent": "PiratesBot-AI-Helper/1.0",
        },
    )

    try:
        with urllib.request.urlopen(api_request, timeout=25) as response:
            payload = json.loads(
                response.read().decode("utf-8", errors="replace")
            )
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:700]
        raise RuntimeError(
            f"OpenAI API HTTP {error.code}: {detail}"
        ) from error

    answer = _pirate_ai_extract_text(payload)
    if not answer:
        raise RuntimeError("OpenAI returned an empty response")

    return answer[:1900]


def _pirate_helper_fallback(question):
    """Basic help continues to work even if the AI API is unavailable."""
    q = question.casefold()

    matches = [
        (("balance", "wallet", "how much money"), "`/balance` shows your wallet and bank."),
        (("send money", "pay someone", "give money"), "Use `/pay member:@User amount:500`."),
        (("blackjack",), "Use `/blackjack bet:500`."),
        (("roulette",), "Use `/roulette amount:500 choice:red`."),
        (("slots", "slot machine"), "Use `/slots bet:500`."),
        (("daily",), "Use `/daily`."),
        (("earn money", "work"), "Use `/work`."),
        (("jobs", "job list", "career"), "Use `/jobs`, then `/choosejob job:<job id>`."),
        (("jobwork", "work my job", "job work"), "Use `/jobwork`."),
        (("job info", "job progress"), "Use `/jobinfo`."),
        (("deadside link", "link deadside"), "Use `/ds link gamertag:YourGamertag`."),
        (("deadside stats", "ds stats"), "Use `/ds stats` or `/dsstats`."),
        (("deadside session",), "Use `/ds session` or `/session`."),
        (("deadside bounty",), "Use `/ds bounty_create gamertag:Player amount:500`."),
        (("dayz link", "link dayz"), "Use `/dz link gamertag:YourGamertag`."),
        (("whereami", "where am i", "coordinates"), "For DayZ use `/dz whereami`."),
        (("dayz stats",), "Use `/dz stats`."),
        (("dayz bounty",), "Use `/dz bounty gamertag:Player amount:500`."),
        (("buy", "shop", "purchase"), "For the DayZ shop use `/buy item:<key> quantity:1`."),
        (("dashboard", "website"), "Dashboard: https://amusing-inspiration-production-eab1.up.railway.app/"),
    ]

    for keywords, answer in matches:
        if any(keyword in q for keyword in keywords):
            return f"☠️ **Pirate Helper**\n{answer}"

    return (
        "☠️ **Pirate Helper**\n"
        "I couldn't find a confident Pirates Bot command for that. "
        "Check the help guide or ask an administrator."
    )


async def process_pirate_ai_helper(message):
    content = str(message.content or "").strip()

    # Only trigger when a message starts with the standalone word Pirate.
    match = re.match(r"(?is)^pirate\b[\s,:-]*(.*)$", content)
    if not match:
        return False

    if PIRATE_AI_CHANNEL_IDS and str(message.channel.id) not in PIRATE_AI_CHANNEL_IDS:
        return False

    question = match.group(1).strip()

    if not question:
        await message.reply(
            "☠️ **Pirate Helper**\n"
            "Ask me something like:\n"
            "`Pirate what command do I use for blackjack?`",
            mention_author=False,
        )
        return True

    question = question[:PIRATE_AI_MAX_QUESTION]

    user_key = (str(message.guild.id), str(message.author.id))
    now = time.monotonic()
    last_used = _pirate_ai_last_used.get(user_key, 0.0)
    remaining = PIRATE_AI_COOLDOWN - (now - last_used)

    if remaining > 0:
        await message.reply(
            f"☠️ Give me **{max(1, int(remaining))}s** before asking again.",
            mention_author=False,
            delete_after=6,
        )
        return True

    _pirate_ai_last_used[user_key] = now

    async with message.channel.typing():
        try:
            if OPENAI_API_KEY:
                answer = await asyncio.to_thread(
                    _pirate_ai_request,
                    question,
                    _pirate_live_commands(),
                )
            else:
                answer = _pirate_helper_fallback(question)

        except Exception as error:
            print(f"Pirate AI Helper error: {error}")
            answer = _pirate_helper_fallback(question)

    await message.reply(
        answer,
        mention_author=False,
        allowed_mentions=discord.AllowedMentions.none(),
    )

    return True


# =========================================================
# MESSAGE EVENT
# =========================================================

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    guild_id = str(message.guild.id)

    data = load_json(
        MODERATION_FILE,
        {
            "guilds": {}
        }
    )

    moderation = (
        data.get("guilds", {})
        .get(guild_id, {})
    )

    automod = moderation.get(
        "automod",
        {}
    )

    if (
        moderation.get("enabled")
        and automod.get("enabled")
    ):
        content_lower = message.content.lower()
        should_delete = False
        reason = ""

        discord_invite_regex = re.compile(
            r"(?:https?://)?(?:www\.)?"
            r"(?:discord(?:app)?\.com/invite|discord\.gg)/\S+",
            re.IGNORECASE
        )

        invite_match = discord_invite_regex.search(
            message.content
        )

        # Discord invite filter
        if (
            automod.get("anti_discord_links")
            and invite_match
        ):
            detected_invite = (
                invite_match.group(0)
                .lower()
                .replace("https://", "")
                .replace("http://", "")
                .replace("www.", "")
                .rstrip("/")
            )

            allowed_invites = [
                str(invite)
                .lower()
                .replace("https://", "")
                .replace("http://", "")
                .replace("www.", "")
                .rstrip("/")
                for invite in automod.get(
                    "allowed_discord_invites",
                    []
                )
            ]

            if detected_invite not in allowed_invites:
                should_delete = True
                reason = (
                    "That Discord invite is not allowed."
                )

        # Banned word filter
        if automod.get("word_filter"):
            banned_words = automod.get(
                "banned_words",
                []
            )

            for banned_word in banned_words:
                banned_word = str(
                    banned_word
                ).strip().lower()

                if (
                    banned_word
                    and banned_word in content_lower
                ):
                    should_delete = True
                    reason = (
                        "That message contains "
                        "a filtered word or phrase."
                    )
                    break

        # Basic spam filter
        if (
            automod.get("anti_spam")
            and len(message.content) > 1200
        ):
            should_delete = True
            reason = (
                "That message was detected as spam."
            )

        if should_delete:
            try:
                await message.delete()

                warning = await message.channel.send(
                    f"{message.author.mention} ⚠️ {reason}"
                )

                await asyncio.sleep(4)
                await warning.delete()

            except discord.Forbidden:
                pass

            except discord.NotFound:
                pass

            return

    # Pirate AI Helper — only messages beginning with `Pirate`.
    if await process_pirate_ai_helper(message):
        return

    # Update activity tracking
    activity = load_activity()
    uid = str(message.author.id)

    activity.setdefault(
        uid,
        {
            "messages": 0
        }
    )

    activity[uid]["messages"] += 1
    save_activity(activity)

    # Repost the configured sticky message
    await process_sticky_message(message)

    # Allow prefix commands to continue working
    await bot.process_commands(message)


sticky_locks = {}


async def process_sticky_message(
    message: discord.Message
):
    if not message.guild:
        return

    data = load_json(
        STICKY_FILE,
        {
            "guilds": {}
        }
    )

    guild_data = (
        data.get("guilds", {})
        .get(str(message.guild.id), {})
    )

    channels = guild_data.get(
        "channels",
        {}
    )

    sticky = channels.get(
        str(message.channel.id)
    )

    if not sticky or not sticky.get(
        "enabled",
        False
    ):
        return

    channel_id = message.channel.id

    if sticky_locks.get(channel_id):
        return

    sticky_locks[channel_id] = True

    try:
        old_message_id = sticky.get(
            "message_id"
        )

        if old_message_id:
            try:
                old_message = await message.channel.fetch_message(
                    int(old_message_id)
                )

                await old_message.delete()

            except (
                discord.NotFound,
                discord.Forbidden,
                ValueError
            ):
                pass

        sticky_message = await message.channel.send(
            sticky.get(
                "message",
                "📌 This is a sticky message."
            )
        )

        sticky["message_id"] = str(
            sticky_message.id
        )

        save_json(
            STICKY_FILE,
            data
        )

    finally:
        sticky_locks[channel_id] = False

# =========================================================
# CUSTOM DASHBOARD TICKET SYSTEM
# =========================================================

DEFAULT_TICKET_DATA = {
    "enabled": True,
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


def load_ticket_settings() -> dict:
    try:
        with open(TICKET_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}

    if not isinstance(data, dict):
        data = {}

    data.setdefault("enabled", True)
    data.setdefault("ticket_channel", "")
    data.setdefault("panel_message_id", "")
    data.setdefault("selection_type", "buttons")
    data.setdefault("option_count", 0)
    data.setdefault("panel", {})
    data.setdefault("settings", {})
    data.setdefault("options", [])

    panel = data["panel"]
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

    settings = data["settings"]
    settings.setdefault(
        "close_message",
        "🔒 This ticket is now being closed."
    )
    settings.setdefault("delete_after_close", True)

    if not isinstance(data["options"], list):
        data["options"] = []

    return data


def save_ticket_settings(data: dict) -> None:
    with open(TICKET_FILE, "w", encoding="utf-8") as file:
        json.dump(
            data,
            file,
            indent=4,
            ensure_ascii=False
        )


def clean_ticket_channel_name(value: str) -> str:
    value = str(value or "").lower().strip()
    value = re.sub(r"[^a-z0-9-]", "-", value)
    value = re.sub(r"-+", "-", value)
    return value.strip("-")[:90] or "ticket"


def ticket_button_style(value: str):
    styles = {
        "blue": discord.ButtonStyle.primary,
        "green": discord.ButtonStyle.success,
        "red": discord.ButtonStyle.danger,
        "grey": discord.ButtonStyle.secondary,
        "gray": discord.ButtonStyle.secondary
    }

    return styles.get(
        str(value).lower(),
        discord.ButtonStyle.secondary
    )


def active_ticket_options():
    data = load_ticket_settings()

    return [
        (index, option)
        for index, option in enumerate(
            data.get("options", [])
        )
        if option.get("enabled", True)
    ]
  
async def create_dashboard_ticket(
    interaction: discord.Interaction,
    option_index: int
):
    ticket_data = load_ticket_settings()
    options = ticket_data.get("options", [])

    if option_index < 0 or option_index >= len(options):
        await interaction.response.send_message(
            "❌ This ticket option no longer exists.",
            ephemeral=True
        )
        return

    option = options[option_index]

    if not option.get("enabled", True):
        await interaction.response.send_message(
            "❌ This ticket option is currently disabled.",
            ephemeral=True
        )
        return

    guild = interaction.guild
    user = interaction.user

    if guild is None:
        await interaction.response.send_message(
            "❌ Tickets can only be opened inside a server.",
            ephemeral=True
        )
        return

    ticket_type = clean_ticket_channel_name(
        option.get("name", f"ticket-{option_index + 1}")
    )

    ticket_topic = (
        f"pirates-ticket:"
        f"{option_index}:"
        f"{user.id}"
    )

    existing_ticket = discord.utils.find(
        lambda channel: (
            isinstance(channel, discord.TextChannel)
            and channel.topic == ticket_topic
        ),
        guild.text_channels
    )

    if existing_ticket:
        await interaction.response.send_message(
            f"❌ You already have this ticket open: "
            f"{existing_ticket.mention}",
            ephemeral=True
        )
        return

    category = None

    category_id = str(
        option.get("category_id", "")
    ).strip()

    if category_id.isdigit():
        possible_category = guild.get_channel(
            int(category_id)
        )

        if isinstance(
            possible_category,
            discord.CategoryChannel
        ):
            category = possible_category

    if category is None:
        category_name = str(
            option.get("category_name", "Tickets")
        ).strip() or "Tickets"

        category = discord.utils.get(
            guild.categories,
            name=category_name
        )

        if category is None:
            category = await guild.create_category(
                category_name,
                reason="Pirates Bot ticket category"
            )

    bot_member = guild.me

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(
            view_channel=False
        ),
        user: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            attach_files=True
        )
    }

    if bot_member is not None:
        overwrites[bot_member] = (
            discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_channels=True,
                manage_messages=True
            )
        )

    staff_role = None

    staff_role_id = str(
        option.get("staff_role_id", "")
    ).strip()

    if staff_role_id.isdigit():
        staff_role = guild.get_role(
            int(staff_role_id)
        )

    if staff_role is not None:
        overwrites[staff_role] = (
            discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_messages=True
            )
        )

    channel_prefix = clean_ticket_channel_name(
        option.get("channel_prefix")
        or option.get("name")
        or "ticket"
    )

    channel_name = clean_ticket_channel_name(
        f"{channel_prefix}-{user.display_name}"
    )

    channel = await guild.create_text_channel(
        name=channel_name,
        category=category,
        topic=ticket_topic,
        overwrites=overwrites,
        reason=(
            f"{option.get('name', 'Ticket')} "
            f"opened by {user}"
        )
    )

    opening_message = str(
        option.get(
            "opening_message",
            "Welcome {user}. Please explain how we can help."
        )
    )

    opening_message = opening_message.replace(
        "{user}",
        user.mention
    )

    opening_message = opening_message.replace(
        "{type}",
        str(option.get("name", "Ticket"))
    )

    embed = discord.Embed(
        title=(
            f"{option.get('emoji', '🎟')} "
            f"{option.get('name', 'Ticket')}"
        ),
        description=opening_message,
        colour=parse_colour(
            option.get("embed_color", "991111")
        )
    )

    embed.add_field(
        name="Opened by",
        value=user.mention,
        inline=True
    )

    embed.add_field(
        name="Ticket type",
        value=str(
            option.get("name", "Ticket")
        ),
        inline=True
    )

    embed.set_footer(
        text="Use the button below when the ticket is resolved."
    )

    mentions = [user.mention]

    if staff_role is not None:
        mentions.append(staff_role.mention)

    await channel.send(
        content=" ".join(mentions),
        embed=embed,
        view=CloseTicketView()
    )

    await interaction.response.send_message(
        f"✅ Your ticket was created: "
        f"{channel.mention}",
        ephemeral=True
    )
class TicketButton(discord.ui.Button):
    def __init__(
        self,
        option_index: int,
        option: dict,
        row: int
    ):
        super().__init__(
            label=str(
                option.get(
                    "name",
                    f"Ticket {option_index + 1}"
                )
            )[:80],
            emoji=option.get("emoji") or None,
            style=ticket_button_style(
                option.get("button_color", "grey")
            ),
            custom_id=f"pirates:ticket:{option_index}",
            row=row
        )

        self.option_index = option_index

    async def callback(
        self,
        interaction: discord.Interaction
    ):
        await create_dashboard_ticket(
            interaction,
            self.option_index
        )


class TicketButtonsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

        enabled_options = active_ticket_options()

        for display_index, (
            option_index,
            option
        ) in enumerate(enabled_options[:25]):

            row = display_index // 5

            self.add_item(
                TicketButton(
                    option_index=option_index,
                    option=option,
                    row=row
                )
            )


class TicketDropdown(discord.ui.Select):
    def __init__(self):
        ticket_data = load_ticket_settings()
        panel = ticket_data.get("panel", {})

        dropdown_options = []

        for option_index, option in active_ticket_options():
            dropdown_options.append(
                discord.SelectOption(
                    label=str(
                        option.get(
                            "name",
                            f"Ticket {option_index + 1}"
                        )
                    )[:100],
                    value=str(option_index),
                    description=str(
                        option.get(
                            "description",
                            "Open this ticket"
                        )
                    )[:100],
                    emoji=option.get("emoji") or None
                )
            )

        if not dropdown_options:
            dropdown_options.append(
                discord.SelectOption(
                    label="No ticket options configured",
                    value="none",
                    description=(
                        "Configure ticket options "
                        "from the dashboard"
                    ),
                    emoji="⚠️"
                )
            )

        super().__init__(
            placeholder=str(
                panel.get(
                    "placeholder",
                    "Choose a ticket type..."
                )
            )[:150],
            min_values=1,
            max_values=1,
            options=dropdown_options[:25],
            custom_id="pirates:ticket_dropdown"
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):
        selected_value = self.values[0]

        if selected_value == "none":
            await interaction.response.send_message(
                "❌ No ticket options are configured.",
                ephemeral=True
            )
            return

        await create_dashboard_ticket(
            interaction,
            int(selected_value)
        )


class TicketDropdownView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketDropdown())


class CloseTicketButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Close Ticket",
            emoji="🔒",
            style=discord.ButtonStyle.danger,
            custom_id="pirates:close_ticket"
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):
        channel = interaction.channel

        if not isinstance(
            channel,
            discord.TextChannel
        ):
            await interaction.response.send_message(
                "❌ This button only works in ticket channels.",
                ephemeral=True
            )
            return

        if not (
            channel.topic
            and channel.topic.startswith(
                "pirates-ticket:"
            )
        ):
            await interaction.response.send_message(
                "❌ This is not a Pirates Bot ticket channel.",
                ephemeral=True
            )
            return

        ticket_data = load_ticket_settings()
        settings = ticket_data.get("settings", {})

        close_message = str(
            settings.get(
                "close_message",
                "🔒 This ticket is now being closed."
            )
        )

        delete_after_close = settings.get(
            "delete_after_close",
            True
        )

        await interaction.response.send_message(
            close_message
        )

        if delete_after_close:
            await asyncio.sleep(3)

            try:
                await channel.delete(
                    reason=(
                        "Pirates Bot ticket closed by "
                        f"{interaction.user}"
                    )
                )
            except discord.Forbidden:
                await interaction.followup.send(
                    "❌ I do not have permission "
                    "to delete this channel.",
                    ephemeral=True
                )

        else:
            closed_name = clean_ticket_channel_name(
                f"closed-{channel.name}"
            )

            try:
                await channel.edit(
                    name=closed_name,
                    reason=(
                        "Pirates Bot ticket closed by "
                        f"{interaction.user}"
                    )
                )

                for member, overwrite in (
                    channel.overwrites.items()
                ):
                    if isinstance(member, discord.Member):
                        if member.id != interaction.guild.me.id:
                            overwrite.send_messages = False

                            await channel.set_permissions(
                                member,
                                overwrite=overwrite
                            )

            except discord.Forbidden:
                await interaction.followup.send(
                    "❌ I do not have permission "
                    "to lock this channel.",
                    ephemeral=True
                )


class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(CloseTicketButton())
# =========================================================
# AUTO ANNOUNCEMENTS
# =========================================================

@tasks.loop(minutes=1)
async def auto_announcement_loop():
    data = load_json(
        ANNOUNCEMENTS_FILE,
        {
            "guilds": {}
        }
    )

    changed = False
    current_time = datetime.now(
        timezone.utc
    ).timestamp()

    for guild_id, guild_data in data.get(
        "guilds",
        {}
    ).items():
        if not guild_data.get(
            "enabled",
            False
        ):
            continue

        for announcement in guild_data.get(
            "announcements",
            []
        ):
            if not announcement.get(
                "enabled",
                False
            ):
                continue

            interval = max(
                60,
                int(
                    announcement.get(
                        "interval",
                        3600
                    )
                )
            )

            last_sent = float(
                announcement.get(
                    "last_sent",
                    0
                )
            )

            if (
                current_time - last_sent
                < interval
            ):
                continue

            try:
                guild = bot.get_guild(
                    int(guild_id)
                )

                if not guild:
                    continue

                channel = guild.get_channel(
                    int(
                        announcement.get(
                            "channel_id",
                            0
                        )
                    )
                )

                if not channel:
                    continue

                await channel.send(
                    announcement.get(
                        "message",
                        "📢 Announcement"
                    )
                )

                announcement["last_sent"] = (
                    current_time
                )

                changed = True

            except (
                TypeError,
                ValueError,
                discord.Forbidden,
                discord.HTTPException
            ):
                continue

    if changed:
        save_json(
            ANNOUNCEMENTS_FILE,
            data
        )


@auto_announcement_loop.before_loop
async def before_auto_announcements():
    await bot.wait_until_ready()
    # =========================================================
# REMINDER COMMAND
# =========================================================

@tree.command(
    name="remindme",
    description="Create a personal reminder"
)
@app_commands.describe(
    minutes="How many minutes until the reminder",
    message="What should I remind you about?"
)
async def remindme(
    interaction: discord.Interaction,
    minutes: app_commands.Range[int, 1, 10080],
    message: str
):
    reminder_data = load_json(
        REMINDERS_FILE,
        {
            "reminders": []
        }
    )

    reminders = reminder_data.setdefault(
        "reminders",
        []
    )

    reminder_id = secrets.token_hex(8)

    due_at = (
        time.time()
        + minutes * 60
    )

    reminders.append({
        "id": reminder_id,
        "guild_id": (
            str(interaction.guild.id)
            if interaction.guild
            else None
        ),
        "channel_id": str(
            interaction.channel_id
        ),
        "user_id": str(
            interaction.user.id
        ),
        "message": message[:1000],
        "due_at": due_at
    })

    save_json(
        REMINDERS_FILE,
        reminder_data
    )

    await interaction.response.send_message(
        (
            f"⏰ I will remind you in "
            f"**{minutes} minute"
            f"{'s' if minutes != 1 else ''}**.\n"
            f"**Reminder:** {message[:1000]}"
        ),
        ephemeral=True
    )
    # =========================================================
# REMINDER LOOP
# =========================================================

@tasks.loop(seconds=30)
async def reminder_loop():
    reminder_data = load_json(
        REMINDERS_FILE,
        {
            "reminders": []
        }
    )

    reminders = reminder_data.get(
        "reminders",
        []
    )

    current_time = time.time()
    remaining_reminders = []
    changed = False

    for reminder in reminders:
        due_at = float(
            reminder.get(
                "due_at",
                0
            )
        )

        if due_at > current_time:
            remaining_reminders.append(
                reminder
            )
            continue

        try:
            channel = bot.get_channel(
                int(
                    reminder.get(
                        "channel_id",
                        0
                    )
                )
            )

            if channel is None:
                changed = True
                continue

            await channel.send(
                (
                    f"<@{reminder.get('user_id')}> ⏰ "
                    f"**Reminder:** "
                    f"{reminder.get('message', 'No reminder text.')}"
                )
            )

            changed = True

        except (
            TypeError,
            ValueError,
            discord.Forbidden,
            discord.HTTPException
        ):
            changed = True

    if changed:
        reminder_data["reminders"] = (
            remaining_reminders
        )

        save_json(
            REMINDERS_FILE,
            reminder_data
        )


@reminder_loop.before_loop
async def before_reminder_loop():
    await bot.wait_until_ready()
# =========================================================
# ROLE MANAGER COMMANDS
# =========================================================

@tree.command(
    name="roleadd",
    description="Admin: Add a role to a member"
)
@app_commands.checks.has_permissions(
    manage_roles=True
)
@app_commands.describe(
    user="Member receiving the role",
    role="Role to add"
)
async def roleadd(
    interaction: discord.Interaction,
    user: discord.Member,
    role: discord.Role
):
    if interaction.guild is None:
        await interaction.response.send_message(
            "❌ This command can only be used in a server.",
            ephemeral=True
        )
        return

    bot_member = interaction.guild.me

    if bot_member is None:
        await interaction.response.send_message(
            "❌ I could not check my role permissions.",
            ephemeral=True
        )
        return

    if role.is_default():
        await interaction.response.send_message(
            "❌ The @everyone role cannot be assigned.",
            ephemeral=True
        )
        return

    if role >= bot_member.top_role:
        await interaction.response.send_message(
            "❌ I cannot manage that role. Move my bot role above it.",
            ephemeral=True
        )
        return

    if role in user.roles:
        await interaction.response.send_message(
            f"❌ {user.mention} already has {role.mention}.",
            ephemeral=True
        )
        return

    try:
        await user.add_roles(
            role,
            reason=(
                f"Role added by "
                f"{interaction.user}"
            )
        )

        await interaction.response.send_message(
            f"✅ Added {role.mention} to {user.mention}."
        )

    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ I do not have permission to add that role.",
            ephemeral=True
        )


@tree.command(
    name="roleremove",
    description="Admin: Remove a role from a member"
)
@app_commands.checks.has_permissions(
    manage_roles=True
)
@app_commands.describe(
    user="Member losing the role",
    role="Role to remove"
)
async def roleremove(
    interaction: discord.Interaction,
    user: discord.Member,
    role: discord.Role
):
    if interaction.guild is None:
        await interaction.response.send_message(
            "❌ This command can only be used in a server.",
            ephemeral=True
        )
        return

    bot_member = interaction.guild.me

    if bot_member is None:
        await interaction.response.send_message(
            "❌ I could not check my role permissions.",
            ephemeral=True
        )
        return

    if role.is_default():
        await interaction.response.send_message(
            "❌ The @everyone role cannot be removed.",
            ephemeral=True
        )
        return

    if role >= bot_member.top_role:
        await interaction.response.send_message(
            "❌ I cannot manage that role. Move my bot role above it.",
            ephemeral=True
        )
        return

    if role not in user.roles:
        await interaction.response.send_message(
            f"❌ {user.mention} does not have {role.mention}.",
            ephemeral=True
        )
        return

    try:
        await user.remove_roles(
            role,
            reason=(
                f"Role removed by "
                f"{interaction.user}"
            )
        )

        await interaction.response.send_message(
            f"✅ Removed {role.mention} from {user.mention}."
        )

    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ I do not have permission to remove that role.",
            ephemeral=True
        )
# ------------------- ECONOMY -------------------
@tree.command(name="balance", description="Check balance")
async def balance(interaction: discord.Interaction):
    users = get_bank()
    u = users.get(str(interaction.user.id), {"wallet": 0, "bank": 0})
    await interaction.response.send_message(
        f"💰 Wallet: ${u['wallet']} | 🏦 Bank: ${u['bank']}"
    )

@tree.command(name="work", description="Work to earn money")
@app_commands.checks.cooldown(1, 600)
async def work(interaction: discord.Interaction):
    earn = random.randint(10, 100)
    update_bank(interaction.user.id, earn)
    await interaction.response.send_message(
        f"🛠 You earned ${earn}"
    )

@tree.command(name="daily", description="Claim daily reward")
@app_commands.checks.cooldown(1, 86400)
async def daily(interaction: discord.Interaction):
    update_bank(interaction.user.id, DAILY_REWARD)
    await interaction.response.send_message(f"🎁 You received ${DAILY_REWARD}")

@tree.command(name="deposit")
async def deposit(interaction: discord.Interaction, amount: int):
    users = get_bank()
    uid = str(interaction.user.id)
    if amount > users.get(uid, {}).get("wallet", 0):
        return await interaction.response.send_message("❌ Not enough money")
    update_bank(interaction.user.id, -amount)
    update_bank(interaction.user.id, amount, bank=True)
    await interaction.response.send_message(f"🏦 Deposited ${amount}")

@tree.command(name="withdraw")
async def withdraw(interaction: discord.Interaction, amount: int):
    users = get_bank()
    uid = str(interaction.user.id)
    if amount > users.get(uid, {}).get("bank", 0):
        return await interaction.response.send_message("❌ Not enough in bank")
    update_bank(interaction.user.id, -amount, bank=True)
    update_bank(interaction.user.id, amount)
    await interaction.response.send_message(f"💸 Withdrew ${amount}")

@tree.command(name="slots")
@app_commands.checks.cooldown(1, 30)
async def slots(interaction: discord.Interaction, bet: int):
    users = get_bank()
    if bet > users.get(str(interaction.user.id), {}).get("wallet", 0):
        return await interaction.response.send_message("❌ Not enough money")

    emojis = ["🍒","🍋","🍊","🍇","💎"]
    result = [random.choice(emojis) for _ in range(3)]
    update_bank(interaction.user.id, -bet)

    if len(set(result)) == 1:
        win = bet * 5
        update_bank(interaction.user.id, win)
        msg = f"{''.join(result)} 🎉 Won ${win}"
    elif len(set(result)) == 2:
        win = bet * 2
        update_bank(interaction.user.id, win)
        msg = f"{''.join(result)} 👍 Won ${win}"
    else:
        msg = f"{''.join(result)} ❌ Lost ${bet}"

    await interaction.response.send_message(msg)
    
    # =========================================================
# ADMIN ECONOMY COMMANDS
# =========================================================

ACCOUNT_CHOICES = [
    app_commands.Choice(
        name="Cash / Wallet",
        value="wallet"
    ),
    app_commands.Choice(
        name="Bank",
        value="bank"
    )
]


@tree.command(
    name="addmoney",
    description="Admin: Add money to a member"
)
@app_commands.checks.has_permissions(
    administrator=True
)
@app_commands.describe(
    user="Member receiving the money",
    amount="Amount of money to add",
    account="Choose cash or bank"
)
@app_commands.choices(
    account=ACCOUNT_CHOICES
)
async def addmoney(
    interaction: discord.Interaction,
    user: discord.Member,
    amount: int,
    account: app_commands.Choice[str]
):
    if amount <= 0:
        await interaction.response.send_message(
            "❌ The amount must be greater than zero.",
            ephemeral=True
        )
        return

    users = get_bank()
    user_id = str(user.id)

    users.setdefault(
        user_id,
        {
            "wallet": 0,
            "bank": 0,
            "last_daily": None
        }
    )

    account_key = account.value
    users[user_id][account_key] = (
        users[user_id].get(account_key, 0)
        + amount
    )

    save_json(
        "bank.json",
        users
    )

    account_name = (
        "cash"
        if account_key == "wallet"
        else "bank"
    )

    await interaction.response.send_message(
        f"✅ Added **${amount:,}** to "
        f"{user.mention}'s **{account_name}**."
    )


@tree.command(
    name="removemoney",
    description="Admin: Remove money from a member"
)
@app_commands.checks.has_permissions(
    administrator=True
)
@app_commands.describe(
    user="Member losing the money",
    amount="Amount of money to remove",
    account="Choose cash or bank"
)
@app_commands.choices(
    account=ACCOUNT_CHOICES
)
async def removemoney(
    interaction: discord.Interaction,
    user: discord.Member,
    amount: int,
    account: app_commands.Choice[str]
):
    if amount <= 0:
        await interaction.response.send_message(
            "❌ The amount must be greater than zero.",
            ephemeral=True
        )
        return

    users = get_bank()
    user_id = str(user.id)

    users.setdefault(
        user_id,
        {
            "wallet": 0,
            "bank": 0,
            "last_daily": None
        }
    )

    account_key = account.value
    current_balance = users[user_id].get(
        account_key,
        0
    )

    removed_amount = min(
        amount,
        current_balance
    )

    users[user_id][account_key] = max(
        0,
        current_balance - amount
    )

    save_json(
        "bank.json",
        users
    )

    account_name = (
        "cash"
        if account_key == "wallet"
        else "bank"
    )

    await interaction.response.send_message(
        f"✅ Removed **${removed_amount:,}** from "
        f"{user.mention}'s **{account_name}**."
    )

@tree.command(
    name="economywipe",
    description="Admin: Reset a member's entire economy balance"
)
@app_commands.checks.has_permissions(
    administrator=True
)
@app_commands.describe(
    user="Member whose economy data will be reset"
)
async def economywipe(
    interaction: discord.Interaction,
    user: discord.Member
):
    users = get_bank()
    user_id = str(user.id)

    users[user_id] = {
        "wallet": 0,
        "bank": 0,
        "last_daily": None
    }

    save_json(
        "bank.json",
        users
    )

    await interaction.response.send_message(
        f"🗑️ {user.mention}'s economy data was reset.\n"
        f"**Cash:** $0\n"
        f"**Bank:** $0"
    )
# ------------------- REACTION ROLES -------------------
@tree.command(name="setreactionrole")
async def setreactionrole(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    message_id: str,
    emoji: str,
    role: discord.Role
):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("Admin only", ephemeral=True)

    roles = get_reaction_roles()
    gid = str(interaction.guild.id)
    roles.setdefault(gid, {}).setdefault(message_id, {})[emoji] = role.id
    update_reaction_roles(roles)

    await interaction.response.send_message("✅ Reaction role set")

# ------------------- FLAG TRANSLATOR -------------------
# React to a message with one of these flags to post a translation in the same server channel.
FLAG_TRANSLATIONS = {
    "🇫🇷": ("FR", "French"),
    "🇩🇪": ("DE", "German"),
    "🇪🇸": ("ES", "Spanish"),
    "🇮🇹": ("IT", "Italian"),
    "🇵🇹": ("PT-PT", "Portuguese"),
    "🇧🇷": ("PT-BR", "Brazilian Portuguese"),
    "🇬🇧": ("EN-GB", "English (UK)"),
    "🇺🇸": ("EN-US", "English (US)"),
    "🇳🇱": ("NL", "Dutch"),
    "🇵🇱": ("PL", "Polish"),
    "🇷🇺": ("RU", "Russian"),
    "🇺🇦": ("UK", "Ukrainian"),
    "🇯🇵": ("JA", "Japanese"),
    "🇨🇳": ("ZH-HANS", "Chinese (Simplified)"),
    "🇰🇷": ("KO", "Korean"),
    "🇹🇷": ("TR", "Turkish"),
    "🇸🇦": ("AR", "Arabic"),
}

DEEPL_API_KEY = os.getenv("DEEPL_API_KEY", "").strip()
DEEPL_API_URL = os.getenv(
    "DEEPL_API_URL",
    "https://api-free.deepl.com/v2/translate"
).strip()
TRANSLATION_COOLDOWN = {}


def _deepl_translate_sync(text: str, target_language: str) -> dict:
    if not DEEPL_API_KEY:
        raise RuntimeError("DEEPL_API_KEY is not configured on the bot service.")

    body = json.dumps({
        "text": [text],
        "target_lang": target_language
    }).encode("utf-8")

    api_request = urllib.request.Request(
        DEEPL_API_URL,
        data=body,
        method="POST",
        headers={
            "Authorization": f"DeepL-Auth-Key {DEEPL_API_KEY}",
            "Content-Type": "application/json",
            "User-Agent": "PiratesBot-Translator/1.0"
        }
    )

    try:
        with urllib.request.urlopen(api_request, timeout=15) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Translation API returned HTTP {error.code}: {details[:300]}"
        ) from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise RuntimeError(f"Translation API connection failed: {error}") from error

    translations = result.get("translations", [])
    if not translations:
        raise RuntimeError("The translation API returned no translation.")

    return translations[0]


async def translate_reacted_message(payload) -> bool:
    emoji = str(payload.emoji)
    language = FLAG_TRANSLATIONS.get(emoji)
    if language is None or payload.guild_id is None:
        return False

    if bot.user and payload.user_id == bot.user.id:
        return True

    target_code, target_name = language
    cooldown_key = (payload.user_id, payload.message_id, target_code)
    now = time.monotonic()
    if now - TRANSLATION_COOLDOWN.get(cooldown_key, 0) < 10:
        return True
    TRANSLATION_COOLDOWN[cooldown_key] = now

    channel = bot.get_channel(payload.channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(payload.channel_id)
        except discord.HTTPException:
            return True

    try:
        message = await channel.fetch_message(payload.message_id)
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        return True

    source_text = str(message.content or "").strip()
    if not source_text:
        return True

    # Keep requests and Discord embeds at a safe size.
    source_text = source_text[:4000]

    guild = bot.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id) if guild else None
    if member is None and guild is not None:
        try:
            member = await guild.fetch_member(payload.user_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            member = None

    if member is None:
        return True

    try:
        translated = await asyncio.to_thread(
            _deepl_translate_sync,
            source_text,
            target_code
        )

        translated_text = str(translated.get("text", "")).strip()
        detected = str(
            translated.get("detected_source_language", "Unknown")
        ).upper()

        embed = discord.Embed(
            title=f"{emoji} Translation to {target_name}",
            description=translated_text[:4096],
            colour=discord.Color.blurple()
        )
        embed.add_field(
            name="Original message",
            value=source_text[:1024],
            inline=False
        )
        embed.set_footer(
            text=f"Detected language: {detected} • #{getattr(channel, 'name', 'channel')}"
        )

        embed.set_author(
            name=f"Requested by {member.display_name}",
            icon_url=member.display_avatar.url
        )

        # Post the translation directly under the original message in the server.
        await message.reply(
            embed=embed,
            mention_author=False,
            allowed_mentions=discord.AllowedMentions.none()
        )
    except Exception as error:
        print(f"Translator error: {error}")
        try:
            await message.reply(
                content=f"❌ Translation failed: {error}",
                mention_author=False,
                allowed_mentions=discord.AllowedMentions.none(),
                delete_after=15
            )
        except discord.HTTPException:
            pass

    # Remove the user's flag so they can request the same translation again.
    try:
        await message.remove_reaction(payload.emoji, member)
    except (discord.Forbidden, discord.HTTPException):
        pass

    return True


@bot.event
async def on_raw_reaction_add(payload):
    # Translator and reaction roles intentionally share this single event handler.
    await translate_reacted_message(payload)

    all_roles = get_reaction_roles()
    role_id = None
    if "roles" in all_roles:
        if str(all_roles.get("message_id", "")) == str(payload.message_id):
            for item in all_roles.get("roles", []):
                if str(item.get("emoji")) == str(payload.emoji):
                    role_id = item.get("role_id")
                    break
    else:
        guild_roles = all_roles.get(str(payload.guild_id), {})
        role_id = guild_roles.get(str(payload.message_id), {}).get(str(payload.emoji))
    if not role_id:
        return
    guild = bot.get_guild(payload.guild_id)
    if guild is None:
        return
    member = guild.get_member(payload.user_id)
    if member is None or member.bot:
        return
    role = guild.get_role(int(role_id)) if str(role_id).isdigit() else None
    if role:
        await member.add_roles(role)

@bot.event
async def on_raw_reaction_remove(payload):
    all_roles = get_reaction_roles()
    role_id = None
    if "roles" in all_roles:
        if str(all_roles.get("message_id", "")) == str(payload.message_id):
            for item in all_roles.get("roles", []):
                if str(item.get("emoji")) == str(payload.emoji):
                    role_id = item.get("role_id")
                    break
    else:
        guild_roles = all_roles.get(str(payload.guild_id), {})
        role_id = guild_roles.get(str(payload.message_id), {}).get(str(payload.emoji))
    if not role_id:
        return
    guild = bot.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)
    role = guild.get_role(int(role_id)) if str(role_id).isdigit() else None
    if role:
        await member.remove_roles(role)

# ------------------- WELCOME -------------------
@bot.event
async def on_member_join(member):
    data = get_welcome_settings().get(str(member.guild.id))
    if not data:
        return
    channel = member.guild.get_channel(data["channel"])
    if not channel:
        return

    msg = data["message"].replace("{user}", member.mention).replace("{server}", member.guild.name)
    if data.get("image"):
        embed = discord.Embed(description=msg, color=discord.Color.green())
        embed.set_image(url=data["image"])
        await channel.send(embed=embed)
    else:
        await channel.send(msg)

# ------------------- ERROR HANDLER (ADDED) -------------------
@tree.error
async def on_app_command_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.CommandOnCooldown):
        await interaction.response.send_message(
            f"⏳ Try again in {int(error.retry_after)}s",
            ephemeral=True
        )
    elif isinstance(error, app_commands.CheckFailure):
        await interaction.response.send_message(
            "❌ You do not have permission",
            ephemeral=True
        )
    else:
        raise error
        # ------------------- PAY -------------------
@tree.command(name="pay", description="Pay another member")
@app_commands.describe(member="Member", amount="Amount")
async def pay(interaction: discord.Interaction, member: discord.Member, amount: int):
    users = get_bank()
    payer = str(interaction.user.id)

    if amount <= 0:
        return await interaction.response.send_message("❌ Invalid amount")

    if amount > users.get(payer, {}).get("wallet", 0):
        return await interaction.response.send_message("❌ Not enough money")

    update_bank(interaction.user.id, -amount)
    update_bank(member.id, amount)

    await interaction.response.send_message(
        f"💸 {interaction.user.mention} paid {member.mention} ${amount}"
    )

# ------------------- ROB -------------------
@tree.command(name="rob", description="Rob another member")
@app_commands.checks.cooldown(1, 900)  # 15 min cooldown
@app_commands.describe(member="Member")
async def rob(interaction: discord.Interaction, member: discord.Member):
    if member.bot:
        return await interaction.response.send_message("❌ You can't rob bots")

    users = get_bank()
    victim_wallet = users.get(str(member.id), {}).get("wallet", 0)

    if victim_wallet <= 0:
        return await interaction.response.send_message("❌ They have no money")

    robbed = random.randint(10, min(50, victim_wallet))
    update_bank(member.id, -robbed)
    update_bank(interaction.user.id, robbed)

    await interaction.response.send_message(
        f"🦹 {interaction.user.mention} robbed {member.mention} for ${robbed}"
    )

# ------------------- LEADERBOARD -------------------
@tree.command(name="leaderboard", description="Top balances")
async def leaderboard(interaction: discord.Interaction):
    users = get_bank()
    sorted_users = sorted(
        users.items(),
        key=lambda x: x[1]["wallet"] + x[1]["bank"],
        reverse=True
    )[:10]

    msg = "🏆 **Leaderboard**\n"
    for i, (uid, data) in enumerate(sorted_users, start=1):
        user = bot.get_user(int(uid))
        name = user.name if user else uid
        total = data["wallet"] + data["bank"]
        msg += f"**{i}.** {name} — ${total}\n"

    await interaction.response.send_message(msg)

# ------------------- BLACKJACK -------------------
class BlackjackView(discord.ui.View):
    def __init__(self, user, bet):
        super().__init__(timeout=120)
        self.user = user
        self.bet = bet
        self.player = [random.randint(1, 11), random.randint(1, 11)]
        self.dealer = [random.randint(1, 11), random.randint(1, 11)]

    def value(self, hand):
        return sum(hand)

    async def update(self, interaction):
        await interaction.response.edit_message(
            content=(
                f"🃏 Your hand: {self.player} ({self.value(self.player)})\n"
                f"Dealer shows: {self.dealer[0]}"
            ),
            view=self
        )

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.green)
    async def hit(self, interaction: discord.Interaction, _):
        if interaction.user != self.user:
            return
        self.player.append(random.randint(1, 11))
        if self.value(self.player) > 21:
            update_bank(self.user.id, -self.bet)
            await interaction.response.edit_message(
                content=f"💥 Bust! Lost ${self.bet}\nHand: {self.player}",
                view=None
            )
            self.stop()
        else:
            await self.update(interaction)

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.red)
    async def stand(self, interaction: discord.Interaction, _):
        if interaction.user != self.user:
            return
        while self.value(self.dealer) < 17:
            self.dealer.append(random.randint(1, 11))

        p, d = self.value(self.player), self.value(self.dealer)

        if d > 21 or p > d:
            update_bank(self.user.id, self.bet * 2)
            msg = f"🎉 You won ${self.bet}\nDealer: {self.dealer} ({d})"
        elif p == d:
            msg = f"🤝 Draw\nDealer: {self.dealer} ({d})"
        else:
            update_bank(self.user.id, -self.bet)
            msg = f"❌ You lost ${self.bet}\nDealer: {self.dealer} ({d})"

        await interaction.response.edit_message(content=msg, view=None)
        self.stop()

@tree.command(name="blackjack", description="Play blackjack")
@app_commands.checks.cooldown(1, 45)
@app_commands.describe(bet="Bet")
async def blackjack(interaction: discord.Interaction, bet: int):
    users = get_bank()
    if bet > users.get(str(interaction.user.id), {}).get("wallet", 0):
        return await interaction.response.send_message("❌ Not enough money")

    view = BlackjackView(interaction.user, bet)
    await interaction.response.send_message(
        f"🃏 Your hand: {view.player} ({sum(view.player)})\nDealer shows: {view.dealer[0]}",
        view=view
    )

# ------------------- ROULETTE -------------------
@tree.command(name="roulette", description="Play roulette")
@app_commands.checks.cooldown(1, 60)
@app_commands.describe(amount="Bet", choice="Red / Black / Green / 0-36")
async def roulette(interaction: discord.Interaction, amount: int, choice: str):
    users = get_bank()
    if amount > users.get(str(interaction.user.id), {}).get("wallet", 0):
        return await interaction.response.send_message("❌ Not enough money")

    colors = {i: "red" if i % 2 == 0 else "black" for i in range(1, 37)}
    colors[0] = "green"
    winning = random.randint(0, 36)

    update_bank(interaction.user.id, -amount)

    if choice.lower() in colors.values() and colors[winning] == choice.lower():
        win = amount * 2
        update_bank(interaction.user.id, win)
        msg = f"🎡 {winning} ({colors[winning]}) — Won ${win}"
    elif choice.isdigit() and int(choice) == winning:
        win = amount * 36
        update_bank(interaction.user.id, win)
        msg = f"🎯 Exact hit! Won ${win}"
    else:
        msg = f"🎡 {winning} ({colors[winning]}) — Lost ${amount}"

    await interaction.response.send_message(msg)

# ------------------- WELCOME COMMANDS -------------------
@tree.command(name="setwelcome")
async def setwelcome(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    message: str,
    image_url: str = None
):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("Admin only", ephemeral=True)

    data = get_welcome_settings()
    data[str(interaction.guild.id)] = {
        "channel": channel.id,
        "message": message,
        "image": image_url
    }
    update_welcome_settings(data)
    await interaction.response.send_message("✅ Welcome message set")

@tree.command(name="removewelcome")
async def removewelcome(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("Admin only", ephemeral=True)

    data = get_welcome_settings()
    data.pop(str(interaction.guild.id), None)
    update_welcome_settings(data)
    await interaction.response.send_message("✅ Welcome removed")

# ------------------- REMOVE ALL MESSAGES -------------------
@tree.command(name="removeallmsgs", description="Delete all messages in a channel")
async def removeallmsgs(interaction: discord.Interaction, channel: discord.TextChannel):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("Admin only", ephemeral=True)

    await interaction.response.send_message(f"🧹 Clearing {channel.mention}...")
    await channel.purge()
    await interaction.followup.send("✅ Done!")
    
# ------------------- AUTO ROLE SYSTEM -------------------
def get_auto_roles():
    try:
        with open("autoroles.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def update_auto_roles(data):
    with open("autoroles.json", "w") as f:
        json.dump(data, f)

@tree.command(name="setautorole", description="Set a role to give automatically to new members")
@app_commands.describe(role="Role to assign automatically")
async def setautorole(interaction: discord.Interaction, role: discord.Role):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Admin only", ephemeral=True)

    data = get_auto_roles()
    data[str(interaction.guild.id)] = role.id
    update_auto_roles(data)
    await interaction.response.send_message(f"✅ Auto role set to {role.name}")

@tree.command(name="removeautorole", description="Remove the auto role")
async def removeautorole(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Admin only", ephemeral=True)

    data = get_auto_roles()
    data.pop(str(interaction.guild.id), None)
    update_auto_roles(data)
    await interaction.response.send_message("✅ Auto role removed")
# ------------------- EVENT: APPLY AUTO ROLE -------------------
@bot.event
async def on_member_join(member):
    # Existing welcome system
    all_welcome = get_welcome_settings()
    welcome_data = all_welcome.get(str(member.guild.id)) if str(member.guild.id) in all_welcome else all_welcome
    if welcome_data and welcome_data.get("enabled", True):
        channel_value = welcome_data.get("channel", welcome_data.get("channel_id", ""))
        channel = member.guild.get_channel(int(channel_value)) if str(channel_value).isdigit() else None
        if channel:
            content = str(welcome_data.get("message", "Welcome {user} to {server}!"))
            content = content.replace("{user}", member.mention).replace("{server}", member.guild.name)
            image_url = welcome_data.get("banner_url") or welcome_data.get("image_url") or welcome_data.get("image")
            if image_url:
                embed = discord.Embed(description=content, color=discord.Color.red())
                embed.set_image(url=image_url)
                await channel.send(embed=embed)
            else:
                await channel.send(content)

            dm_settings = welcome_data.get("dm", {})
            if dm_settings.get("enabled"):
                try:
                    dm_text = str(dm_settings.get("message", content)).replace("{user}", member.name).replace("{server}", member.guild.name)
                    await member.send(dm_text)
                except discord.Forbidden:
                    pass

    # Apply auto role
    autoroles = get_auto_roles()
    role_id = autoroles.get(str(member.guild.id))
    if role_id:
        role = member.guild.get_role(role_id)
        if role:
            try:
                await member.add_roles(role)
            except Exception as e:
                print(f"Failed to add auto role: {e}")
                
# ------------------- ADMIN ECONOMY MANAGEMENT -------------------
@tree.command(name="money", description="Admin: Add, remove, or reset money for a member")
@app_commands.describe(
    member="The member to modify",
    action="Action to perform: add, remove, or reset",
    amount="Amount to add or remove (ignored if reset)"
)
async def money(interaction: discord.Interaction, member: discord.Member, action: str, amount: int = 0):
    # Check if admin
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Admin only", ephemeral=True)
    
    users = get_bank()
    user_id = str(member.id)
    if user_id not in users:
        users[user_id] = {"wallet": 0, "bank": 0, "last_daily": None}

    action = action.lower()
    if action == "add":
        users[user_id]["wallet"] += amount
        update_bank(member.id, 0)  # Save changes to file
        await interaction.response.send_message(f"✅ Added ${amount} to {member.mention}'s wallet.")
    elif action == "remove":
        users[user_id]["wallet"] -= amount
        if users[user_id]["wallet"] < 0:
            users[user_id]["wallet"] = 0
        update_bank(member.id, 0)  # Save changes to file
        await interaction.response.send_message(f"✅ Removed ${amount} from {member.mention}'s wallet.")
    elif action == "reset":
        users[user_id]["wallet"] = 0
        users[user_id]["bank"] = 0
        update_bank(member.id, 0)  # Save changes to file
        await interaction.response.send_message(f"✅ Reset {member.mention}'s wallet and bank to $0.")
    else:
        await interaction.response.send_message("❌ Invalid action! Use `add`, `remove`, or `reset`.", ephemeral=True)
    
    # Save all changes back to JSON
    with open("bank.json", "w") as f:
        json.dump(users, f)

# ------------------- VIEW OTHER USER BALANCE -------------------
@tree.command(name="balanceof", description="View another member's wallet and bank balance")
@app_commands.describe(member="The member to check")
async def balanceof(interaction: discord.Interaction, member: discord.Member):
    users = get_bank()
    data = users.get(str(member.id), {"wallet": 0, "bank": 0})

    await interaction.response.send_message(
        f"💰 **{member.display_name}'s Balance**\n"
        f"Wallet: **${data['wallet']}**\n"
        f"Bank: **${data['bank']}**"
    )
# ------------------- DASHBOARD LIVE APPLY -------------------
def _read_config(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return {} if default is None else default


def _write_config(path, data):
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)


def _find_text_channel(channel_id):
    value = str(channel_id or "").strip()
    if not value.isdigit():
        return None
    channel = bot.get_channel(int(value))
    return channel if isinstance(channel, discord.TextChannel) else None


async def _send_or_edit(channel, config, message_key, *, content=None, embed=None, view=None):
    message = None
    message_id = str(config.get(message_key, "")).strip()
    if message_id.isdigit():
        try:
            message = await channel.fetch_message(int(message_id))
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            message = None
    if message:
        await message.edit(content=content, embed=embed, view=view)
    else:
        message = await channel.send(content=content, embed=embed, view=view)
        config[message_key] = str(message.id)
    return message



# ------------------- DEADSIDE KILLFEED -------------------
DEADSIDE_DEFAULT_KILL_PATTERN = (
    r"(?P<killer>.+?)\\s+(?:killed|eliminated)\\s+(?P<victim>.+?)"
    r"(?:\\s+with\\s+(?P<weapon>.+?))?(?:\\s+at\\s+(?P<distance>\\d+(?:\\.\\d+)?)m)?$"
)


def _deadside_servers():
    data = _read_config(DEADSIDE_FILE, {"servers": {}})
    servers = data.get("servers", {})
    return servers if isinstance(servers, dict) else {}


def _deadside_join_path(directory, name):
    directory = str(directory or "").strip().replace("\\", "/")
    name = str(name or "").strip().replace("\\", "/")
    if not directory:
        return name
    return posixpath.join(directory.rstrip("/"), name.lstrip("/"))


def _deadside_log_directory(config):
    return (
        str(config.get("death_logs_directory", "")).strip()
        or str(config.get("deadside_log_path", "")).strip()
        or "."
    )


def _deadside_matches_log(name, config):
    pattern = str(config.get("log_file_pattern", "*.log")).strip() or "*.log"
    patterns = [item.strip() for item in pattern.split(",") if item.strip()]
    return any(fnmatch.fnmatch(posixpath.basename(name).lower(), item.lower()) for item in patterns)


def _deadside_decode(data):
    if isinstance(data, str):
        return data
    for encoding in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            return data.decode(encoding)
        except (UnicodeDecodeError, AttributeError):
            continue
    return bytes(data).decode("utf-8", errors="replace")


def _deadside_fetch_http(config):
    url = str(config.get("feed_url", "")).strip()
    if not url.startswith(("http://", "https://")):
        raise RuntimeError("The feed URL must start with http:// or https://")
    headers = {"User-Agent": "PiratesBot-Deadside/2.0"}
    token = str(config.get("auth_token", "")).strip()
    header_name = str(config.get("auth_header", "Authorization")).strip() or "Authorization"
    if token:
        headers[header_name] = token
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as response:
        return _deadside_decode(response.read())


def _deadside_fetch_ftp(config, secure=False):
    host = str(config.get("host", "")).strip()
    username = str(config.get("username", "")).strip()
    password = str(config.get("password", ""))
    port = int(config.get("port") or (21 if not secure else 21))
    if not host or not username or not password:
        raise RuntimeError("Host, username and password are required for FTP/FTPS.")

    client_class = ftplib.FTP_TLS if secure else ftplib.FTP
    client = client_class(timeout=20)
    try:
        client.connect(host, port)
        client.login(username, password)
        if secure:
            client.prot_p()
        directory = _deadside_log_directory(config)
        client.cwd(directory)

        entries = []
        try:
            for name, facts in client.mlsd():
                if facts.get("type") == "file" and _deadside_matches_log(name, config):
                    entries.append((facts.get("modify", ""), name))
        except (ftplib.error_perm, AttributeError):
            for name in client.nlst():
                if _deadside_matches_log(name, config):
                    entries.append(("", name))

        if not entries:
            raise RuntimeError(f"No matching death log files were found in {directory!r}.")
        entries.sort(key=lambda item: (item[0], item[1]))
        max_files = max(1, min(int(config.get("max_log_files", 5) or 5), 25))
        chunks = []
        for _, name in entries[-max_files:]:
            buffer = io.BytesIO()
            client.retrbinary(f"RETR {name}", buffer.write)
            chunks.append(_deadside_decode(buffer.getvalue()))
        return "\n".join(chunks)
    finally:
        try:
            client.quit()
        except Exception:
            try:
                client.close()
            except Exception:
                pass


def _deadside_fetch_sftp(config):
    try:
        import paramiko
    except ImportError as error:
        raise RuntimeError(
            "SFTP requires Paramiko. Add paramiko>=3.4,<4 to requirements.txt and redeploy."
        ) from error

    host = str(config.get("host", "")).strip()
    username = str(config.get("username", "")).strip()
    password = str(config.get("password", ""))
    port = int(config.get("port") or 22)
    if not host or not username or not password:
        raise RuntimeError("Host, username and password are required for SFTP.")

    transport = paramiko.Transport((host, port))
    transport.banner_timeout = 20
    transport.auth_timeout = 20
    try:
        transport.connect(username=username, password=password)
        sftp = paramiko.SFTPClient.from_transport(transport)
        try:
            directory = _deadside_log_directory(config)
            entries = []
            for entry in sftp.listdir_attr(directory):
                if _deadside_matches_log(entry.filename, config):
                    entries.append((int(entry.st_mtime or 0), entry.filename))
            if not entries:
                raise RuntimeError(f"No matching death log files were found in {directory!r}.")
            entries.sort(key=lambda item: (item[0], item[1]))
            max_files = max(1, min(int(config.get("max_log_files", 5) or 5), 25))
            chunks = []
            for _, name in entries[-max_files:]:
                remote_path = _deadside_join_path(directory, name)
                with sftp.open(remote_path, "rb") as remote_file:
                    chunks.append(_deadside_decode(remote_file.read()))
            return "\n".join(chunks)
        finally:
            sftp.close()
    finally:
        transport.close()


def _deadside_fetch_admin_sync(config):
    admin_directory = str(config.get("admin_logs_directory", "")).strip()
    if not admin_directory:
        return ""
    admin_config = dict(config)
    admin_config["death_logs_directory"] = admin_directory
    admin_config["deadside_log_path"] = admin_directory
    admin_config["log_file_pattern"] = str(
        config.get("admin_log_file_pattern", "*.log,*.txt,*.csv")
    ).strip() or "*.log,*.txt,*.csv"
    return _deadside_fetch_sync(admin_config)


def _deadside_parse_admin_events(raw):
    events = []
    for line in str(raw or "").splitlines():
        text = line.strip()
        if not text:
            continue
        lower = text.lower()
        action = None
        if any(word in lower for word in ("spawned", "spawn item", "giveitem", "give item")):
            action = "spawn_item"
        if any(word in lower for word in ("spawn vehicle", "spawned vehicle", "vehicle spawned")):
            action = "spawn_vehicle"
        elif "teleport" in lower:
            action = "teleport"
        elif any(word in lower for word in (" kicked ", "kick player", "was kicked")):
            action = "kick"
        elif any(word in lower for word in (" banned ", "ban player", "was banned", "unban")):
            action = "ban"
        elif any(word in lower for word in ("god mode", "godmode", "invulnerab")):
            action = "godmode"
        if not action:
            continue
        digest = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()
        events.append({"id": digest, "action": action, "raw": text})
    return events


async def _post_deadside_admin_event(config, event):
    channel = _find_text_channel(config.get("admin_log_channel"))
    if not channel:
        return
    enabled_map = {
        "spawn_item": config.get("admin_show_spawns", True),
        "spawn_vehicle": config.get("admin_show_vehicles", True),
        "teleport": config.get("admin_show_teleports", True),
        "kick": config.get("admin_show_kicks", True),
        "ban": config.get("admin_show_bans", True),
        "godmode": config.get("admin_show_godmode", True),
    }
    if not enabled_map.get(event.get("action"), True):
        return
    labels = {
        "spawn_item": "📦 Item Spawn",
        "spawn_vehicle": "🚙 Vehicle Spawn",
        "teleport": "🧭 Teleport",
        "kick": "👢 Player Kick",
        "ban": "🔨 Ban Action",
        "godmode": "🛡️ God Mode",
    }
    embed = discord.Embed(
        title=labels.get(event.get("action"), "🛠️ Admin Action"),
        description=f"```\n{str(event.get('raw', ''))[:3800]}\n```",
        colour=discord.Color.orange(),
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_footer(text=str(config.get("server_name", "Deadside Server"))[:2048])
    await channel.send(embed=embed)


def _deadside_fetch_sync(config):
    protocol = str(
        config.get("protocol")
        or config.get("connection_method")
        or "ftps"
    ).lower().strip()

    if protocol not in {"ftps", "ftp_tls", "ftp-tls"}:
        raise RuntimeError(
            "This Deadside integration supports GPORTAL FTPS only."
        )

    return _deadside_fetch_ftp(config, secure=True)



def _deadside_parse_events(raw, config):
    events = []
    raw = raw.strip()
    if not raw:
        return events
    # JSON feeds may return a list or {events:[...]}. Field names are configurable by convention.
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        parsed = parsed.get("events", parsed.get("kills", []))
    if isinstance(parsed, list):
        for item in parsed:
            if not isinstance(item, dict):
                continue
            killer = str(item.get("killer") or item.get("attacker") or "Unknown")
            victim = str(item.get("victim") or item.get("killed") or "Unknown")
            event_id = str(item.get("id") or item.get("event_id") or json.dumps(item, sort_keys=True))
            events.append({
                "id": event_id,
                "killer": killer,
                "victim": victim,
                "weapon": str(item.get("weapon") or "Unknown"),
                "distance": str(item.get("distance") or ""),
                "headshot": bool(item.get("headshot", False)),
                "raw": item,
            })
        return events

    pattern = str(config.get("kill_pattern") or DEADSIDE_DEFAULT_KILL_PATTERN)
    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error as error:
        raise RuntimeError(f"Invalid kill log regex: {error}")
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        match = regex.search(line)
        if not match:
            continue
        groups = match.groupdict()
        events.append({
            "id": line,
            "killer": groups.get("killer") or "Unknown",
            "victim": groups.get("victim") or "Unknown",
            "weapon": groups.get("weapon") or "Unknown",
            "distance": groups.get("distance") or "",
            "headshot": bool(groups.get("headshot")),
            "raw": line,
        })
    return events


def _deadside_state():
    data = _read_config(DEADSIDE_STATE_FILE, {"seen": {}})
    data.setdefault("seen", {})
    return data



def _deadside_stats():
    data = _read_config(DEADSIDE_STATS_FILE, {"servers": {}})
    data.setdefault("servers", {})
    return data


def _update_deadside_stats(stats_root, guild_id, event):
    server = stats_root["servers"].setdefault(str(guild_id), {"players": {}, "leaderboard_message_id": "", "last_leaderboard": 0})
    players = server.setdefault("players", {})
    killer_name = str(event.get("killer") or "Unknown")
    victim_name = str(event.get("victim") or "Unknown")
    weapon = str(event.get("weapon") or "Unknown")
    try:
        distance = float(str(event.get("distance") or "0").replace("m", "").strip() or 0)
    except ValueError:
        distance = 0.0
    killer = players.setdefault(killer_name, {"kills": 0, "deaths": 0, "headshots": 0, "streak": 0, "best_streak": 0, "longest_kill": 0, "weapons": {}, "bounties_claimed": 0, "money_earned": 0})
    victim = players.setdefault(victim_name, {"kills": 0, "deaths": 0, "headshots": 0, "streak": 0, "best_streak": 0, "longest_kill": 0, "weapons": {}, "bounties_claimed": 0, "money_earned": 0})
    suicide = killer_name.casefold() == victim_name.casefold()
    victim["deaths"] = int(victim.get("deaths", 0)) + 1
    victim["streak"] = 0
    if not suicide:
        killer["kills"] = int(killer.get("kills", 0)) + 1
        if event.get("headshot"):
            killer["headshots"] = int(killer.get("headshots", 0)) + 1
        killer["streak"] = int(killer.get("streak", 0)) + 1
        killer["best_streak"] = max(int(killer.get("best_streak", 0)), killer["streak"])
        killer["longest_kill"] = max(float(killer.get("longest_kill", 0) or 0), distance)
        weapons = killer.setdefault("weapons", {})
        weapons[weapon] = int(weapons.get(weapon, 0)) + 1



# ------------------- DEADSIDE PLAYER / ECONOMY SUITE -------------------
def _deadside_player_root():
    data = _read_config(DEADSIDE_PLAYERS_FILE, {"guilds": {}})
    data.setdefault("guilds", {})
    return data


def _deadside_bounty_root():
    data = _read_config(DEADSIDE_BOUNTIES_FILE, {"guilds": {}})
    data.setdefault("guilds", {})
    return data


def _deadside_session_root():
    data = _read_config(DEADSIDE_SESSIONS_FILE, {"guilds": {}})
    data.setdefault("guilds", {})
    return data


def _deadside_config_for_guild(guild_id):
    return _deadside_servers().get(str(guild_id), {}) or {}


def _deadside_linked_players(guild_id):
    root = _deadside_player_root()
    guild_data = root["guilds"].setdefault(str(guild_id), {"users": {}})
    guild_data.setdefault("users", {})
    return root, guild_data


def _deadside_find_link_by_gamertag(guild_id, gamertag):
    _, guild_data = _deadside_linked_players(guild_id)
    wanted = str(gamertag or "").strip().casefold()
    for discord_id, record in guild_data.get("users", {}).items():
        if str(record.get("gamertag", "")).strip().casefold() == wanted:
            return str(discord_id), record
    return None, None


def _deadside_find_link_by_discord(guild_id, discord_id):
    _, guild_data = _deadside_linked_players(guild_id)
    return guild_data.get("users", {}).get(str(discord_id))


def _economy_account(users, discord_id):
    uid = str(discord_id)
    users.setdefault(uid, {"wallet": 0, "bank": 0, "last_daily": None})
    users[uid].setdefault("wallet", 0)
    users[uid].setdefault("bank", 0)
    users[uid].setdefault("last_daily", None)
    return users[uid]


def _deadside_add_wallet(discord_id, amount):
    amount = max(0, int(amount))
    if amount <= 0:
        return 0
    users = get_bank()
    account = _economy_account(users, discord_id)
    account["wallet"] = int(account.get("wallet", 0)) + amount
    save_json("bank.json", users)
    return amount


def _deadside_take_wallet(discord_id, amount):
    amount = max(0, int(amount))
    users = get_bank()
    account = _economy_account(users, discord_id)
    wallet = int(account.get("wallet", 0))
    if amount > wallet:
        return False
    account["wallet"] = wallet - amount
    save_json("bank.json", users)
    return True


def _deadside_session_for(guild_id, discord_id, config):
    root = _deadside_session_root()
    guild_data = root["guilds"].setdefault(str(guild_id), {"users": {}})
    users = guild_data.setdefault("users", {})
    now = time.time()
    session_seconds = max(
        300,
        int(config.get("reward_session_minutes", 120) or 120) * 60
    )
    session = users.setdefault(
        str(discord_id),
        {
            "started_at": now,
            "last_event_at": now,
            "kills": 0,
            "deaths": 0,
            "earned": 0,
            "bounties_claimed": 0,
            "headshots": 0,
        }
    )
    if now - float(session.get("started_at", now)) >= session_seconds:
        session = {
            "started_at": now,
            "last_event_at": now,
            "kills": 0,
            "deaths": 0,
            "earned": 0,
            "bounties_claimed": 0,
            "headshots": 0,
        }
        users[str(discord_id)] = session
    return root, session


def _deadside_active_bounties(guild_id):
    root = _deadside_bounty_root()
    guild_data = root["guilds"].setdefault(str(guild_id), {"items": []})
    items = guild_data.setdefault("items", [])
    now = time.time()
    changed = False
    for bounty in items:
        if (
            bounty.get("status") == "active"
            and float(bounty.get("expires_at", 0) or 0) > 0
            and float(bounty["expires_at"]) <= now
        ):
            bounty["status"] = "expired"
            if bounty.get("refund_on_expiry", True):
                _deadside_add_wallet(
                    bounty.get("creator_id"),
                    int(bounty.get("amount", 0))
                )
            changed = True
    if changed:
        _write_config(DEADSIDE_BOUNTIES_FILE, root)
    return root, guild_data, [
        item for item in items if item.get("status") == "active"
    ]


async def _deadside_radar_alert(guild_id, config, *, title, description, colour=0xC13B32):
    if not config.get("radar_enabled", False):
        return
    channel = _find_text_channel(config.get("radar_channel"))
    if not channel:
        return
    embed = discord.Embed(
        title=title[:256],
        description=description[:4096],
        colour=colour,
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_footer(
        text=str(config.get("server_name", "Deadside Server"))[:2048]
    )
    await channel.send(embed=embed)


async def _process_deadside_rewards(guild_id, config, event, stats_root):
    killer_name = str(event.get("killer") or "Unknown").strip()
    victim_name = str(event.get("victim") or "Unknown").strip()
    if not killer_name or killer_name.casefold() == victim_name.casefold():
        return

    killer_id, killer_link = _deadside_find_link_by_gamertag(
        guild_id,
        killer_name
    )
    victim_id, victim_link = _deadside_find_link_by_gamertag(
        guild_id,
        victim_name
    )

    # Record a linked victim death in their current session.
    if victim_id:
        session_root, victim_session = _deadside_session_for(
            guild_id,
            victim_id,
            config
        )
        victim_session["deaths"] = int(victim_session.get("deaths", 0)) + 1
        victim_session["last_event_at"] = time.time()
        _write_config(DEADSIDE_SESSIONS_FILE, session_root)

    reward_paid = 0
    if killer_id:
        session_root, session = _deadside_session_for(
            guild_id,
            killer_id,
            config
        )
        session["kills"] = int(session.get("kills", 0)) + 1
        session["last_event_at"] = time.time()
        if event.get("headshot"):
            session["headshots"] = int(session.get("headshots", 0)) + 1

        if config.get("player_rewards_enabled", False):
            pay_per_kill = max(
                0,
                int(config.get("pay_per_kill", 0) or 0)
            )
            min_pay = max(
                0,
                int(config.get("minimum_kill_payment", 0) or 0)
            )
            max_pay = max(
                min_pay,
                int(config.get("maximum_kill_payment", pay_per_kill) or pay_per_kill)
            )
            reward = max(min_pay, min(pay_per_kill, max_pay))

            if event.get("headshot"):
                reward += max(
                    0,
                    int(config.get("headshot_bonus", 0) or 0)
                )

            session_limit = max(
                0,
                int(config.get("session_payment_limit", 0) or 0)
            )
            already = int(session.get("earned", 0))
            if session_limit:
                reward = min(reward, max(0, session_limit - already))

            if reward > 0:
                reward_paid = _deadside_add_wallet(killer_id, reward)
                session["earned"] = already + reward_paid

        _write_config(DEADSIDE_SESSIONS_FILE, session_root)

    # Claim player-created bounties.
    bounty_root, _, active = _deadside_active_bounties(guild_id)
    claimed = [
        bounty
        for bounty in active
        if str(bounty.get("target_gamertag", "")).strip().casefold()
        == victim_name.casefold()
    ]
    total_bounty = 0
    if killer_id and claimed:
        total_bounty = sum(int(item.get("amount", 0)) for item in claimed)
        if total_bounty > 0:
            _deadside_add_wallet(killer_id, total_bounty)
            for bounty in claimed:
                bounty["status"] = "claimed"
                bounty["claimed_by"] = str(killer_id)
                bounty["claimed_at"] = time.time()
                bounty["claim_event_id"] = str(event.get("id", ""))
            _write_config(DEADSIDE_BOUNTIES_FILE, bounty_root)

            session_root, session = _deadside_session_for(
                guild_id,
                killer_id,
                config
            )
            session["earned"] = int(session.get("earned", 0)) + total_bounty
            session["bounties_claimed"] = (
                int(session.get("bounties_claimed", 0)) + len(claimed)
            )
            _write_config(DEADSIDE_SESSIONS_FILE, session_root)

            await _deadside_radar_alert(
                guild_id,
                config,
                title="💰 Deadside Bounty Claimed",
                description=(
                    f"**{discord.utils.escape_markdown(killer_name)}** claimed "
                    f"**${total_bounty:,}** by eliminating "
                    f"**{discord.utils.escape_markdown(victim_name)}**."
                ),
                colour=0xD5A248,
            )

    # Automatic killstreak reward/bounty.
    server = stats_root.get("servers", {}).get(str(guild_id), {})
    killer_stats = server.get("players", {}).get(killer_name, {})
    streak = int(killer_stats.get("streak", 0))
    threshold = max(
        2,
        int(config.get("killstreak_bounty_start", 5) or 5)
    )
    if config.get("killstreak_bounties_enabled", False) and streak >= threshold:
        step = max(
            1,
            int(config.get("killstreak_bounty_every", 5) or 5)
        )
        if streak == threshold or (streak - threshold) % step == 0:
            starting = max(
                0,
                int(config.get("killstreak_bounty_reward", 250) or 250)
            )
            increase = max(
                0,
                int(config.get("killstreak_bounty_increase", 50) or 50)
            )
            cap = max(
                starting,
                int(config.get("killstreak_bounty_maximum", 5000) or 5000)
            )
            amount = min(
                cap,
                starting + max(0, streak - threshold) * increase
            )

            bounty_root, guild_bounties, active = _deadside_active_bounties(
                guild_id
            )
            auto_id = f"auto:{killer_name.casefold()}"
            existing = next(
                (
                    item for item in active
                    if item.get("id") == auto_id
                ),
                None
            )
            if existing:
                existing["amount"] = amount
                existing["streak"] = streak
                existing["updated_at"] = time.time()
            else:
                guild_bounties["items"].append({
                    "id": auto_id,
                    "creator_id": "system",
                    "target_gamertag": killer_name,
                    "amount": amount,
                    "status": "active",
                    "created_at": time.time(),
                    "expires_at": 0,
                    "refund_on_expiry": False,
                    "automatic": True,
                    "streak": streak,
                })
            _write_config(DEADSIDE_BOUNTIES_FILE, bounty_root)

            await _deadside_radar_alert(
                guild_id,
                config,
                title="🎯 Killstreak Bounty",
                description=(
                    f"**{discord.utils.escape_markdown(killer_name)}** reached "
                    f"a **{streak} kill streak**.\n"
                    f"Current bounty: **${amount:,}**"
                ),
                colour=0xB92E2E,
            )

    if killer_id and reward_paid and config.get("reward_notifications", False):
        guild = bot.get_guild(int(guild_id))
        member = guild.get_member(int(killer_id)) if guild else None
        if member:
            try:
                await member.send(
                    f"☠️ Deadside reward: **${reward_paid:,}** was added to "
                    f"your existing economy wallet for eliminating "
                    f"**{victim_name}**."
                )
            except discord.HTTPException:
                pass


def _deadside_profile_stats(guild_id, gamertag):
    stats_root = _deadside_stats()
    server = stats_root.get("servers", {}).get(str(guild_id), {})
    players = server.get("players", {})
    wanted = str(gamertag or "").strip().casefold()
    for name, data in players.items():
        if str(name).casefold() == wanted:
            return name, data
    return gamertag, {}




# ------------------- ADMIN FORCE PLAYER LINKING -------------------
force_group = app_commands.Group(
    name="force",
    description="Administrator override tools"
)


@force_group.command(
    name="link",
    description="Admin: force-link a Discord member to a Deadside or DayZ gamertag"
)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(
    game="Choose which game integration to link",
    member="Discord member to link",
    gamertag="Exact in-game gamertag",
    guid="Optional DayZ GUID"
)
@app_commands.choices(
    game=[
        app_commands.Choice(name="Deadside", value="deadside"),
        app_commands.Choice(name="DayZ", value="dayz"),
    ]
)
async def force_link(
    interaction: discord.Interaction,
    game: app_commands.Choice[str],
    member: discord.Member,
    gamertag: str,
    guid: str = ""
):
    if interaction.guild is None:
        return await interaction.response.send_message(
            "❌ Use this command inside a Discord server.",
            ephemeral=True,
        )

    gamertag = gamertag.strip()
    guid = guid.strip()

    if not gamertag or len(gamertag) > 80:
        return await interaction.response.send_message(
            "❌ Enter a valid gamertag.",
            ephemeral=True,
        )

    if game.value == "deadside":
        root, guild_data = _deadside_linked_players(interaction.guild_id)
        users = guild_data.setdefault("users", {})

        # Remove this gamertag from anyone else in this Discord server.
        duplicate_ids = [
            discord_id
            for discord_id, record in users.items()
            if discord_id != str(member.id)
            and str(record.get("gamertag", "")).strip().casefold()
            == gamertag.casefold()
        ]
        for discord_id in duplicate_ids:
            users.pop(discord_id, None)

        previous = users.get(str(member.id), {})
        users[str(member.id)] = {
            "gamertag": gamertag,
            "linked_at": time.time(),
            "discord_name": str(member),
            "force_linked": True,
            "force_linked_by": str(interaction.user.id),
            "previous_gamertag": previous.get("gamertag", ""),
        }

        _write_config(DEADSIDE_PLAYERS_FILE, root)

        return await interaction.response.send_message(
            f"✅ Force-linked {member.mention} to Deadside gamertag "
            f"**{discord.utils.escape_markdown(gamertag)}**.",
            ephemeral=True,
        )

    if game.value == "dayz":
        root = _dz_players()
        guild_data = root["guilds"].setdefault(
            str(interaction.guild_id),
            {"users": {}}
        )
        users = guild_data.setdefault("users", {})

        # Remove this gamertag/GUID from anyone else in this Discord server.
        duplicate_ids = []
        for discord_id, record in users.items():
            if discord_id == str(member.id):
                continue

            same_gamertag = (
                str(record.get("gamertag", "")).strip().casefold()
                == gamertag.casefold()
            )
            same_guid = bool(
                guid
                and str(record.get("guid", "")).strip().casefold()
                == guid.casefold()
            )

            if same_gamertag or same_guid:
                duplicate_ids.append(discord_id)

        for discord_id in duplicate_ids:
            users.pop(discord_id, None)

        previous = users.get(str(member.id), {})
        users[str(member.id)] = {
            "gamertag": gamertag,
            "guid": guid,
            "linked_at": time.time(),
            "discord_name": str(member),
            "force_linked": True,
            "force_linked_by": str(interaction.user.id),
            "previous_gamertag": previous.get("gamertag", ""),
            "previous_guid": previous.get("guid", ""),
        }

        _write_config(DAYZ_PLAYERS_FILE, root)

        guid_text = (
            f"\nGUID: `{discord.utils.escape_markdown(guid)}`"
            if guid else ""
        )

        return await interaction.response.send_message(
            f"✅ Force-linked {member.mention} to DayZ gamertag "
            f"**{discord.utils.escape_markdown(gamertag)}**.{guid_text}",
            ephemeral=True,
        )


tree.add_command(force_group)


ds_group = app_commands.Group(
    name="ds",
    description="Deadside player, stats, session and bounty commands"
)


@ds_group.command(name="link", description="Link your Discord account to a Deadside gamertag")
@app_commands.describe(gamertag="Your exact Deadside player name")
async def ds_link(interaction: discord.Interaction, gamertag: str):
    if interaction.guild is None:
        return await interaction.response.send_message(
            "❌ Use this command in a server.",
            ephemeral=True
        )

    gamertag = gamertag.strip()
    if not gamertag or len(gamertag) > 80:
        return await interaction.response.send_message(
            "❌ Enter a valid gamertag.",
            ephemeral=True
        )

    existing_id, _ = _deadside_find_link_by_gamertag(
        interaction.guild_id,
        gamertag
    )
    if existing_id and existing_id != str(interaction.user.id):
        return await interaction.response.send_message(
            "❌ That gamertag is already linked to another Discord account.",
            ephemeral=True
        )

    root, guild_data = _deadside_linked_players(interaction.guild_id)
    guild_data["users"][str(interaction.user.id)] = {
        "gamertag": gamertag,
        "linked_at": time.time(),
        "discord_name": str(interaction.user),
    }
    _write_config(DEADSIDE_PLAYERS_FILE, root)
    await interaction.response.send_message(
        f"✅ Linked {interaction.user.mention} to Deadside gamertag "
        f"**{discord.utils.escape_markdown(gamertag)}**."
    )


@ds_group.command(name="unlink", description="Remove your Deadside gamertag link")
async def ds_unlink(interaction: discord.Interaction):
    if interaction.guild is None:
        return await interaction.response.send_message(
            "❌ Use this command in a server.",
            ephemeral=True
        )
    root, guild_data = _deadside_linked_players(interaction.guild_id)
    removed = guild_data["users"].pop(str(interaction.user.id), None)
    _write_config(DEADSIDE_PLAYERS_FILE, root)
    await interaction.response.send_message(
        "✅ Deadside link removed." if removed else "ℹ️ You had no linked gamertag.",
        ephemeral=True
    )


async def _send_ds_stats(interaction, member=None):
    member = member or interaction.user
    link = _deadside_find_link_by_discord(
        interaction.guild_id,
        member.id
    )
    if not link:
        return await interaction.response.send_message(
            f"❌ {member.mention} has not linked a gamertag. Use `/ds link`.",
            ephemeral=True
        )

    gamertag, data = _deadside_profile_stats(
        interaction.guild_id,
        link.get("gamertag")
    )
    kills = int(data.get("kills", 0))
    deaths = int(data.get("deaths", 0))
    kd = kills / max(1, deaths)
    weapons = data.get("weapons", {})
    favorite = max(weapons, key=weapons.get) if weapons else "None"

    users = get_bank()
    economy = _economy_account(users, member.id)

    embed = discord.Embed(
        title=f"☠️ Deadside Stats — {gamertag}",
        colour=0x991111,
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(name="Kills", value=f"{kills:,}")
    embed.add_field(name="Deaths", value=f"{deaths:,}")
    embed.add_field(name="K/D", value=f"{kd:.2f}")
    embed.add_field(name="Current streak", value=str(data.get("streak", 0)))
    embed.add_field(name="Best streak", value=str(data.get("best_streak", 0)))
    embed.add_field(
        name="Longest kill",
        value=f"{float(data.get('longest_kill', 0) or 0):.1f} m"
    )
    embed.add_field(name="Favourite weapon", value=favorite)
    embed.add_field(
        name="Existing economy",
        value=(
            f"Wallet: **${int(economy.get('wallet', 0)):,}**\n"
            f"Bank: **${int(economy.get('bank', 0)):,}**"
        ),
        inline=False
    )
    await interaction.response.send_message(embed=embed)


@ds_group.command(name="stats", description="Show linked Deadside player statistics")
@app_commands.describe(member="Optional linked Discord member")
async def ds_stats(
    interaction: discord.Interaction,
    member: discord.Member | None = None
):
    await _send_ds_stats(interaction, member)


@ds_group.command(name="session", description="Show your current Deadside earning session")
async def ds_session(interaction: discord.Interaction):
    if interaction.guild is None:
        return await interaction.response.send_message(
            "❌ Use this command in a server.",
            ephemeral=True
        )
    config = _deadside_config_for_guild(interaction.guild_id)
    root, session = _deadside_session_for(
        interaction.guild_id,
        interaction.user.id,
        config
    )
    started = int(float(session.get("started_at", time.time())))
    embed = discord.Embed(
        title="⏱️ Deadside Session",
        colour=0xD5A248,
    )
    embed.description = (
        f"Started: <t:{started}:R>\n"
        f"Kills: **{int(session.get('kills', 0))}**\n"
        f"Deaths: **{int(session.get('deaths', 0))}**\n"
        f"Headshots: **{int(session.get('headshots', 0))}**\n"
        f"Bounties claimed: **{int(session.get('bounties_claimed', 0))}**\n"
        f"Paid into existing wallet: "
        f"**${int(session.get('earned', 0)):,}**"
    )
    await interaction.response.send_message(embed=embed)


@ds_group.command(name="leaderboard", description="Show the Deadside kill leaderboard")
async def ds_leaderboard(interaction: discord.Interaction):
    stats_root = _deadside_stats()
    server = stats_root.get("servers", {}).get(str(interaction.guild_id), {})
    players = server.get("players", {})
    ranked = sorted(
        players.items(),
        key=lambda item: (
            -int(item[1].get("kills", 0)),
            int(item[1].get("deaths", 0)),
        )
    )[:10]
    lines = []
    for index, (name, data) in enumerate(ranked, 1):
        kills = int(data.get("kills", 0))
        deaths = int(data.get("deaths", 0))
        lines.append(
            f"**{index}. {discord.utils.escape_markdown(name)}** — "
            f"{kills} kills • {deaths} deaths • "
            f"{kills / max(1, deaths):.2f} K/D"
        )
    await interaction.response.send_message(
        embed=discord.Embed(
            title="🏆 Deadside Leaderboard",
            description="\n".join(lines) if lines else "No statistics yet.",
            colour=0x991111,
        )
    )


@ds_group.command(name="bounty_create", description="Place a bounty using your existing wallet")
@app_commands.describe(gamertag="Target Deadside gamertag", amount="Bounty amount")
async def ds_bounty_create(
    interaction: discord.Interaction,
    gamertag: str,
    amount: int
):
    config = _deadside_config_for_guild(interaction.guild_id)
    if not config.get("player_bounties_enabled", False):
        return await interaction.response.send_message(
            "❌ Player bounties are disabled.",
            ephemeral=True
        )

    minimum = max(1, int(config.get("minimum_bounty", 100) or 100))
    maximum = max(minimum, int(config.get("maximum_bounty", 10000) or 10000))
    if amount < minimum or amount > maximum:
        return await interaction.response.send_message(
            f"❌ Bounties must be between **${minimum:,}** and **${maximum:,}**.",
            ephemeral=True
        )

    _, _, active = _deadside_active_bounties(interaction.guild_id)
    user_active = [
        item for item in active
        if str(item.get("creator_id")) == str(interaction.user.id)
    ]
    max_active = max(
        1,
        int(config.get("maximum_active_bounties", 3) or 3)
    )
    if len(user_active) >= max_active:
        return await interaction.response.send_message(
            f"❌ You already have {max_active} active bounties.",
            ephemeral=True
        )

    if not _deadside_take_wallet(interaction.user.id, amount):
        return await interaction.response.send_message(
            "❌ You do not have enough money in your existing wallet.",
            ephemeral=True
        )

    root, guild_data, _ = _deadside_active_bounties(interaction.guild_id)
    expiry_hours = max(
        1,
        int(config.get("bounty_expiry_hours", 72) or 72)
    )
    bounty = {
        "id": secrets.token_urlsafe(8),
        "creator_id": str(interaction.user.id),
        "target_gamertag": gamertag.strip(),
        "amount": int(amount),
        "status": "active",
        "created_at": time.time(),
        "expires_at": time.time() + expiry_hours * 3600,
        "refund_on_expiry": config.get("refund_expired_bounties", True),
        "automatic": False,
    }
    guild_data["items"].append(bounty)
    _write_config(DEADSIDE_BOUNTIES_FILE, root)

    await interaction.response.send_message(
        f"🎯 Bounty placed on **{discord.utils.escape_markdown(gamertag)}** "
        f"for **${amount:,}** from your existing wallet."
    )


@ds_group.command(name="bounties", description="List active Deadside bounties")
async def ds_bounties(interaction: discord.Interaction):
    _, _, active = _deadside_active_bounties(interaction.guild_id)
    lines = [
        f"🎯 **{discord.utils.escape_markdown(str(item.get('target_gamertag')))}** "
        f"— **${int(item.get('amount', 0)):,}**"
        for item in sorted(
            active,
            key=lambda item: -int(item.get("amount", 0))
        )[:20]
    ]
    await interaction.response.send_message(
        embed=discord.Embed(
            title="💰 Active Deadside Bounties",
            description="\n".join(lines) if lines else "No active bounties.",
            colour=0xD5A248,
        )
    )


@tree.command(name="dsstats", description="Show your linked Deadside statistics")
@app_commands.describe(member="Optional linked Discord member")
async def deadside_stats_alias(
    interaction: discord.Interaction,
    member: discord.Member | None = None
):
    await _send_ds_stats(interaction, member)


@tree.command(name="session", description="Show your current Deadside earning session")
async def deadside_session_alias(interaction: discord.Interaction):
    await ds_session.callback(interaction)


tree.add_command(ds_group)



# =================== DAYZ / NITRADO INTEGRATION ===================
def _dz_read(path, default):
    data = _read_config(path, default)
    return data if isinstance(data, dict) else default.copy()

def _dz_servers():
    r=_dz_read(DAYZ_FILE,{"servers":{}}); r.setdefault("servers",{}); return r["servers"]

def _dz_stats():
    r=_dz_read(DAYZ_STATS_FILE,{"servers":{}}); r.setdefault("servers",{}); return r

def _dz_state():
    r=_dz_read(DAYZ_STATE_FILE,{"servers":{}}); r.setdefault("servers",{}); return r

def _dz_players():
    r=_dz_read(DAYZ_PLAYERS_FILE,{"guilds":{}}); r.setdefault("guilds",{}); return r

def _dz_bounties():
    r=_dz_read(DAYZ_BOUNTIES_FILE,{"guilds":{}}); r.setdefault("guilds",{}); return r

def _dz_shop():
    r=_dz_read(DAYZ_SHOP_FILE,{"guilds":{}}); r.setdefault("guilds",{}); return r

def _dz_queue():
    r=_dz_read(DAYZ_SPAWN_QUEUE_FILE,{"guilds":{}}); r.setdefault("guilds",{}); return r

def _dz_config(guild_id): return _dz_servers().get(str(guild_id),{}) or {}

def _dz_api(config, path):
    token=str(config.get("nitrado_api_token","")).strip()
    if not token: raise RuntimeError("Nitrado API token is not configured.")
    req=urllib.request.Request(
        f"{str(config.get('nitrado_api_base','https://api.nitrado.net')).rstrip('/')}{path}",
        headers={"Authorization":f"Bearer {token}","Accept":"application/json","User-Agent":"PiratesBot-DayZ/1.0"})
    with urllib.request.urlopen(req,timeout=20) as response:
        return json.loads(response.read().decode("utf-8",errors="replace"))

def _dz_test_nitrado(config):
    sid=str(config.get("nitrado_service_id","")).strip()
    if not sid.isdigit(): raise RuntimeError("Enter a valid Nitrado service ID.")
    return _dz_api(config,f"/services/{sid}/gameservers")

def _dz_fetch_log(config):
    host=str(config.get("ftp_host","")).strip(); user=str(config.get("ftp_username","")).strip()
    password=str(config.get("ftp_password","")); path=str(config.get("admin_log_path","")).strip()
    if not all((host,user,password,path)): raise RuntimeError("Nitrado FTPS host, username, password and admin log path are required.")
    ftp=ftplib.FTP_TLS(timeout=25); ftp.connect(host,int(config.get("ftp_port",21) or 21)); ftp.login(user,password); ftp.prot_p()
    buf=io.BytesIO()
    try: ftp.retrbinary(f"RETR {path}",buf.write)
    finally:
        try: ftp.quit()
        except Exception: pass
    return buf.getvalue().decode("utf-8",errors="replace")

_DZ_KILL=re.compile(r'Player\s+"(?P<victim>[^"]+)".*?id=(?P<victim_id>[^,\)\s]+).*?pos=<(?P<vx>-?\d+(?:\.\d+)?),\s*(?P<vz>-?\d+(?:\.\d+)?),\s*(?P<vy>-?\d+(?:\.\d+)?)>.*?killed by\s+"(?P<killer>[^"]+)".*?id=(?P<killer_id>[^,\)\s]+).*?pos=<(?P<kx>-?\d+(?:\.\d+)?),\s*(?P<kz>-?\d+(?:\.\d+)?),\s*(?P<ky>-?\d+(?:\.\d+)?)>(?:.*?with\s+(?P<weapon>.+?)\s+from\s+(?P<distance>\d+(?:\.\d+)?)\s+meters)?',re.I)
_DZ_DEATH=re.compile(r'Player\s+"(?P<victim>[^"]+)".*?id=(?P<victim_id>[^,\)\s]+).*?pos=<(?P<vx>-?\d+(?:\.\d+)?),\s*(?P<vz>-?\d+(?:\.\d+)?),\s*(?P<vy>-?\d+(?:\.\d+)?)>.*?(?P<reason>killed by Infected|committed suicide|bled out|died\.)',re.I)
_DZ_POS=re.compile(r'Player\s+"(?P<name>[^"]+)"\s*\(id=(?P<guid>[^,\)\s]+)[,\s]+pos=<(?P<x>-?\d+(?:\.\d+)?),\s*(?P<z>-?\d+(?:\.\d+)?),\s*(?P<y>-?\d+(?:\.\d+)?)>',re.I)

def _dz_parse(raw):
    events=[]; positions={}
    for line in raw.splitlines():
        line=line.strip()
        if not line: continue
        p=_DZ_POS.search(line)
        if p:
            g=p.groupdict(); positions[g["guid"]]={"name":g["name"],"guid":g["guid"],"x":float(g["x"]),"z":float(g["z"]),"y":float(g["y"]),"updated_at":time.time()}
        m=_DZ_KILL.search(line)
        if m:
            g=m.groupdict(); events.append({"id":hashlib.sha256(line.encode()).hexdigest(),"type":"kill","killer":g["killer"],"killer_guid":g["killer_id"],"victim":g["victim"],"victim_guid":g["victim_id"],"weapon":(g.get("weapon") or "Unknown").strip(),"distance":float(g.get("distance") or 0),"killer_pos":{"x":float(g["kx"]),"z":float(g["kz"]),"y":float(g["ky"])},"victim_pos":{"x":float(g["vx"]),"z":float(g["vz"]),"y":float(g["vy"])},"raw":line}); continue
        d=_DZ_DEATH.search(line)
        if d:
            g=d.groupdict(); events.append({"id":hashlib.sha256(line.encode()).hexdigest(),"type":"death","victim":g["victim"],"victim_guid":g["victim_id"],"reason":g["reason"],"victim_pos":{"x":float(g["vx"]),"z":float(g["vz"]),"y":float(g["vy"])},"raw":line})
    return events,positions

def _dz_link(guild_id, discord_id=None, guid=None, gamertag=None):
    root=_dz_players(); guild=root["guilds"].setdefault(str(guild_id),{"users":{}}); users=guild.setdefault("users",{})
    if discord_id is not None: return users.get(str(discord_id))
    for uid,r in users.items():
        if guid and str(r.get("guid","")).casefold()==str(guid).casefold(): return uid,r
        if gamertag and str(r.get("gamertag","")).casefold()==str(gamertag).casefold(): return uid,r
    return None,None

def _dz_add_money(uid, amount):
    users=get_bank(); uid=str(uid); users.setdefault(uid,{"wallet":0,"bank":0,"last_daily":None}); users[uid]["wallet"]=int(users[uid].get("wallet",0))+max(0,int(amount)); save_json("bank.json",users)

def _dz_take_money(uid, amount):
    users=get_bank(); uid=str(uid); users.setdefault(uid,{"wallet":0,"bank":0,"last_daily":None}); amount=max(0,int(amount))
    if int(users[uid].get("wallet",0))<amount: return False
    users[uid]["wallet"]-=amount; save_json("bank.json",users); return True

def _dz_update_stats(root,gid,event):
    server=root["servers"].setdefault(str(gid),{"players":{},"positions":{}}); players=server.setdefault("players",{})
    def rec(name,guid): return players.setdefault(name,{"guid":guid,"kills":0,"deaths":0,"streak":0,"best_streak":0,"longest_kill":0,"weapons":{}})
    if event["type"]=="kill":
        k=rec(event["killer"],event.get("killer_guid","")); v=rec(event["victim"],event.get("victim_guid","")); k["kills"]+=1; k["streak"]+=1; k["best_streak"]=max(k["best_streak"],k["streak"]); k["longest_kill"]=max(float(k.get("longest_kill",0)),float(event.get("distance",0))); w=k.setdefault("weapons",{}); w[event.get("weapon","Unknown")]=int(w.get(event.get("weapon","Unknown"),0))+1; v["deaths"]+=1; v["streak"]=0
    else:
        v=rec(event["victim"],event.get("victim_guid","")); v["deaths"]+=1; v["streak"]=0

async def _dz_post(config,event):
    ch=_find_text_channel(config.get("killfeed_channel" if event["type"]=="kill" else "deathfeed_channel"))
    if not ch: return
    colour=parse_colour(config.get("embed_color","991111"))
    if event["type"]=="kill":
        e=discord.Embed(title=str(config.get("killfeed_title","☠️ DayZ Killfeed"))[:256],description=f"**{discord.utils.escape_markdown(event['killer'])}** killed **{discord.utils.escape_markdown(event['victim'])}**",colour=colour,timestamp=datetime.now(timezone.utc))
        if config.get("show_weapon",True): e.add_field(name="Weapon",value=str(event.get("weapon","Unknown"))[:1024])
        if config.get("show_distance",True) and event.get("distance"): e.add_field(name="Distance",value=f"{event['distance']:.1f} m")
        if config.get("show_location",True): p=event.get("victim_pos",{}); e.add_field(name="Location",value=f"X {p.get('x',0):.0f} • Z {p.get('z',0):.0f}",inline=False)
    else:
        e=discord.Embed(title=str(config.get("deathfeed_title","💀 DayZ Deathfeed"))[:256],description=f"**{discord.utils.escape_markdown(event['victim'])}** {event.get('reason','died')}",colour=colour,timestamp=datetime.now(timezone.utc)); p=event.get("victim_pos",{}); e.add_field(name="Location",value=f"X {p.get('x',0):.0f} • Z {p.get('z',0):.0f}",inline=False)
    e.set_footer(text=str(config.get("server_name","DayZ Server"))[:2048]); await ch.send(embed=e)

async def _dz_economy(gid,config,event):
    if event.get("type")!="kill": return
    killer_id,_=_dz_link(gid,guid=event.get("killer_guid"),gamertag=event.get("killer"))
    if killer_id and config.get("pay_per_kill_enabled",False): _dz_add_money(killer_id,int(config.get("pay_per_kill",0) or 0))
    root=_dz_bounties(); guild=root["guilds"].setdefault(str(gid),{"items":[]}); target=str(event.get("victim","")).casefold(); claimed=[b for b in guild.setdefault("items",[]) if b.get("status")=="active" and str(b.get("target_gamertag","")).casefold()==target]
    if killer_id and claimed:
        total=sum(int(b.get("amount",0)) for b in claimed); _dz_add_money(killer_id,total)
        for b in claimed: b.update(status="claimed",claimed_by=str(killer_id),claimed_at=time.time())
        _write_config(DAYZ_BOUNTIES_FILE,root)

def _dz_dist(a,b): return ((float(a["x"])-float(b["x"]))**2+(float(a["z"])-float(b["z"]))**2)**0.5

async def _dz_radar(gid,config,stats,state):
    now=time.time(); interval=max(60,int(config.get("radar_interval_seconds",600) or 600))
    if now-float(state.get("last_radar",0) or 0)<interval: return
    state["last_radar"]=now; positions=stats["servers"].setdefault(str(gid),{"players":{},"positions":{}}).setdefault("positions",{})
    if config.get("radar_enabled",False):
        ch=_find_text_channel(config.get("radar_channel")); center={"x":float(config.get("radar_center_x",0) or 0),"z":float(config.get("radar_center_z",0) or 0)}; radius=max(1,float(config.get("radar_radius",1000) or 1000)); inside=[p for p in positions.values() if _dz_dist(p,center)<=radius]
        if ch and inside:
            rid=str(config.get("radar_ping_role","")).strip(); mention=f"<@&{rid}>" if rid.isdigit() else None; lines=[f"• **{discord.utils.escape_markdown(p['name'])}** — X {p['x']:.0f}, Z {p['z']:.0f}" for p in inside[:25]]; await ch.send(content=mention,embed=discord.Embed(title=f"📡 DayZ Radar — {len(inside)} player(s)",description="\n".join(lines),colour=parse_colour(config.get("embed_color","991111"))))
    ch=_find_text_channel(config.get("bounty_channel")); active=[b for b in _dz_bounties().get("guilds",{}).get(str(gid),{}).get("items",[]) if b.get("status")=="active"]
    if ch:
        for b in active:
            p=next((p for p in positions.values() if str(p.get("name","")).casefold()==str(b.get("target_gamertag","")).casefold()),None)
            if p: await ch.send(embed=discord.Embed(title="🎯 Active DayZ Bounty Location",description=f"**{discord.utils.escape_markdown(p['name'])}**\nLast known: **X {p['x']:.0f}, Z {p['z']:.0f}**\nBounty: **${int(b.get('amount',0)):,}**\n_Position is based on the latest admin-log player list._",colour=0xD5A248,timestamp=datetime.now(timezone.utc)))

@tasks.loop(seconds=30)
async def dayz_log_loop():
    servers=_dz_servers(); state=_dz_state(); stats=_dz_stats(); changed=False; stat_changed=False; now=time.time()
    for gid,config in servers.items():
        if not isinstance(config,dict) or not config.get("enabled"): continue
        s=state["servers"].setdefault(str(gid),{"seen":[],"last_poll":0,"last_radar":0})
        if now-float(s.get("last_poll",0) or 0)<max(30,int(config.get("poll_interval",60) or 60)): continue
        s["last_poll"]=now; changed=True
        try:
            raw=await asyncio.to_thread(_dz_fetch_log,config); events,positions=_dz_parse(raw); seen=set(s.get("seen",[])); new=[e for e in events if e["id"] not in seen]
            if not seen and events: new=[]
            stats["servers"].setdefault(str(gid),{"players":{},"positions":{}}).setdefault("positions",{}).update(positions)
            for event in new[-50:]: await _dz_post(config,event); _dz_update_stats(stats,gid,event); await _dz_economy(gid,config,event); stat_changed=True
            await _dz_radar(gid,config,stats,s); s["seen"]=[e["id"] for e in events[-1000:]]; s.pop("last_error",None)
            if positions: stat_changed=True
        except Exception as error: s["last_error"]=str(error)[:500]; print(f"DayZ poll error for guild {gid}: {error}")
    if changed: _write_config(DAYZ_STATE_FILE,state)
    if stat_changed: _write_config(DAYZ_STATS_FILE,stats)

@dayz_log_loop.before_loop
async def before_dayz_log_loop(): await bot.wait_until_ready()

dz_group=app_commands.Group(name="dz",description="DayZ server and player commands")

@dz_group.command(name="link",description="Link your Discord account to a DayZ gamertag")
@app_commands.describe(gamertag="Exact DayZ player name",guid="DayZ GUID if known")
async def dz_link(interaction:discord.Interaction,gamertag:str,guid:str=""):
    root=_dz_players(); guild=root["guilds"].setdefault(str(interaction.guild_id),{"users":{}}); guild.setdefault("users",{})[str(interaction.user.id)]={"gamertag":gamertag.strip(),"guid":guid.strip(),"linked_at":time.time(),"discord_name":str(interaction.user)}; _write_config(DAYZ_PLAYERS_FILE,root); await interaction.response.send_message(f"✅ Linked {interaction.user.mention} to **{discord.utils.escape_markdown(gamertag)}**.")

@dz_group.command(name="whereami",description="Show your latest DayZ coordinates")
async def dz_whereami(interaction:discord.Interaction):
    link=_dz_link(interaction.guild_id,discord_id=interaction.user.id)
    if not link: return await interaction.response.send_message("❌ Link first with `/dz link`.",ephemeral=True)
    positions=_dz_stats().get("servers",{}).get(str(interaction.guild_id),{}).get("positions",{}); pos=positions.get(str(link.get("guid",""))) or next((p for p in positions.values() if str(p.get("name","")).casefold()==str(link.get("gamertag","")).casefold()),None)
    if not pos: return await interaction.response.send_message("❌ No recent admin-log position is available.",ephemeral=True)
    await interaction.response.send_message(f"📍 **{pos['name']}** — X **{pos['x']:.0f}**, Z **{pos['z']:.0f}**, Y **{pos['y']:.0f}**")

@dz_group.command(name="stats",description="Show DayZ player statistics")
@app_commands.describe(member="Optional linked Discord member")
async def dz_stats(interaction:discord.Interaction,member:discord.Member|None=None):
    member=member or interaction.user; link=_dz_link(interaction.guild_id,discord_id=member.id)
    if not link: return await interaction.response.send_message("❌ That member has no linked DayZ gamertag.",ephemeral=True)
    players=_dz_stats().get("servers",{}).get(str(interaction.guild_id),{}).get("players",{}); data=next((d for n,d in players.items() if n.casefold()==str(link.get("gamertag","")).casefold()),{}); k=int(data.get("kills",0)); d=int(data.get("deaths",0)); weapons=data.get("weapons",{}); fav=max(weapons,key=weapons.get) if weapons else "None"; e=discord.Embed(title=f"🧟 DayZ Stats — {link.get('gamertag')}",colour=0x991111); e.add_field(name="Kills",value=str(k)); e.add_field(name="Deaths",value=str(d)); e.add_field(name="K/D",value=f"{k/max(1,d):.2f}"); e.add_field(name="Current streak",value=str(data.get("streak",0))); e.add_field(name="Best streak",value=str(data.get("best_streak",0))); e.add_field(name="Longest kill",value=f"{float(data.get('longest_kill',0) or 0):.1f} m"); e.add_field(name="Favourite weapon",value=fav,inline=False); await interaction.response.send_message(embed=e)

@dz_group.command(name="leaderboard",description="Show the DayZ kill leaderboard")
async def dz_leaderboard(interaction:discord.Interaction):
    players=_dz_stats().get("servers",{}).get(str(interaction.guild_id),{}).get("players",{}); ranked=sorted(players.items(),key=lambda x:(-int(x[1].get("kills",0)),int(x[1].get("deaths",0))))[:10]; lines=[f"**{i}. {discord.utils.escape_markdown(n)}** — {int(d.get('kills',0))} kills • {int(d.get('deaths',0))} deaths" for i,(n,d) in enumerate(ranked,1)]; await interaction.response.send_message(embed=discord.Embed(title="🏆 DayZ Leaderboard",description="\n".join(lines) if lines else "No stats yet.",colour=0x991111))

@dz_group.command(name="playerlocations",description="Admin: latest DayZ player locations")
@app_commands.checks.has_permissions(administrator=True)
async def dz_playerlocations(interaction:discord.Interaction):
    pos=_dz_stats().get("servers",{}).get(str(interaction.guild_id),{}).get("positions",{}); lines=[f"**{discord.utils.escape_markdown(p['name'])}** — X {p['x']:.0f}, Z {p['z']:.0f}" for p in list(pos.values())[:40]]; await interaction.response.send_message(embed=discord.Embed(title="📍 Latest DayZ Player Locations",description="\n".join(lines) if lines else "No player-list positions yet.",colour=0xD5A248),ephemeral=True)

@dz_group.command(name="bounty",description="Place a DayZ bounty using your shared wallet")
@app_commands.describe(gamertag="Target DayZ gamertag",amount="Bounty amount")
async def dz_bounty(interaction:discord.Interaction,gamertag:str,amount:int):
    cfg=_dz_config(interaction.guild_id); lo=max(1,int(cfg.get("minimum_bounty",100) or 100)); hi=max(lo,int(cfg.get("maximum_bounty",10000) or 10000))
    if not lo<=amount<=hi: return await interaction.response.send_message(f"❌ Bounty must be between ${lo:,} and ${hi:,}.",ephemeral=True)
    if not _dz_take_money(interaction.user.id,amount): return await interaction.response.send_message("❌ Not enough money in your shared wallet.",ephemeral=True)
    root=_dz_bounties(); guild=root["guilds"].setdefault(str(interaction.guild_id),{"items":[]}); guild.setdefault("items",[]).append({"id":secrets.token_urlsafe(8),"creator_id":str(interaction.user.id),"target_gamertag":gamertag.strip(),"amount":int(amount),"status":"active","created_at":time.time()}); _write_config(DAYZ_BOUNTIES_FILE,root); await interaction.response.send_message(f"🎯 **${amount:,}** bounty placed on **{discord.utils.escape_markdown(gamertag)}**.")

@dz_group.command(name="bounties",description="List active DayZ bounties")
async def dz_bounties(interaction:discord.Interaction):
    active=[b for b in _dz_bounties().get("guilds",{}).get(str(interaction.guild_id),{}).get("items",[]) if b.get("status")=="active"]; lines=[f"🎯 **{discord.utils.escape_markdown(str(b.get('target_gamertag')))}** — **${int(b.get('amount',0)):,}**" for b in active[:20]]; await interaction.response.send_message(embed=discord.Embed(title="DayZ Bounties",description="\n".join(lines) if lines else "No active bounties.",colour=0xD5A248))

@dz_group.command(
    name="buy",
    description="Buy a DayZ shop item"
)
@app_commands.describe(
    item_key="Shop item key",
    quantity="How many bundles to buy",
    x="Drop X coordinate when custom locations are enabled",
    z="Drop Z coordinate when custom locations are enabled",
    y="Drop Y/height coordinate; normally 0"
)
async def dz_buy(
    interaction: discord.Interaction,
    item_key: str,
    quantity: app_commands.Range[int, 1, 100] = 1,
    x: float | None = None,
    z: float | None = None,
    y: float = 0.0
):
    if interaction.guild is None:
        return await interaction.response.send_message(
            "❌ Use this command in a server.",
            ephemeral=True
        )

    config = _dayz_config(interaction.guild_id)
    if not config.get("enabled", False):
        return await interaction.response.send_message(
            "❌ DayZ has not been set up for this Discord server yet.",
            ephemeral=True
        )

    shop = _dayz_shop()
    guild = shop["guilds"].setdefault(
        str(interaction.guild_id),
        {
            "settings": {},
            "items": [],
            "vehicles": []
        }
    )
    settings = guild.setdefault("settings", {})
    guild.setdefault("items", [])
    guild.setdefault("vehicles", [])

    if not settings.get("enabled", True):
        return await interaction.response.send_message(
            "❌ The DayZ online shop is currently disabled.",
            ephemeral=True
        )

    item = next(
        (
            entry for entry in guild["items"]
            if str(entry.get("key", "")).casefold() == item_key.strip().casefold()
            and entry.get("enabled", True)
        ),
        None
    )

    if not item:
        return await interaction.response.send_message(
            "❌ That item is not available in the DayZ shop.",
            ephemeral=True
        )

    max_per_purchase = max(1, int(item.get("max_per_purchase", 10) or 10))
    if quantity > max_per_purchase:
        return await interaction.response.send_message(
            f"❌ You can buy a maximum of **{max_per_purchase}** at once.",
            ephemeral=True
        )

    stock = int(item.get("stock", -1) or -1)
    if stock >= 0 and quantity > stock:
        return await interaction.response.send_message(
            f"❌ Only **{stock}** bundle(s) are currently in stock.",
            ephemeral=True
        )

    allow_custom = bool(item.get("allow_custom_location", False))
    if allow_custom:
        if x is None or z is None:
            return await interaction.response.send_message(
                "❌ This item requires a drop location. Enter both **X** and **Z**.",
                ephemeral=True
            )
        drop_x = float(x)
        drop_z = float(z)
        drop_y = float(y or 0)
        location_name = "Custom coordinates"
    else:
        try:
            drop_x = float(item["x"])
            drop_z = float(item["z"])
            drop_y = float(item.get("y", 0) or 0)
        except (KeyError, TypeError, ValueError):
            return await interaction.response.send_message(
                "❌ This shop item has no valid delivery coordinates configured.",
                ephemeral=True
            )
        location_name = (
            str(item.get("location_name", "")).strip()
            or str(settings.get("default_location_name", "")).strip()
            or "Configured drop point"
        )

    unit_price = max(0, int(item.get("price", 0) or 0))
    total_price = unit_price * quantity
    bundle_quantity = max(1, int(item.get("quantity", 1) or 1))
    total_units = bundle_quantity * quantity

    if not _dayz_wallet_take(interaction.user.id, total_price):
        return await interaction.response.send_message(
            "❌ You do not have enough money in your shared economy wallet.",
            ephemeral=True
        )

    # Reduce finite stock only after payment succeeds.
    if stock >= 0:
        item["stock"] = stock - quantity
        _write_config(DAYZ_SHOP_FILE, shop)

    queue = _dayz_spawn_queue()
    qguild = queue["guilds"].setdefault(
        str(interaction.guild_id),
        {"requests": []}
    )

    request_id = secrets.token_urlsafe(8)
    qguild.setdefault("requests", []).append({
        "id": request_id,
        "type": "item_delivery",
        "discord_id": str(interaction.user.id),
        "discord_name": str(interaction.user),
        "item_key": str(item.get("key", "")),
        "class_name": item.get("class_name"),
        "display_name": item.get("display_name"),
        "bundles": quantity,
        "quantity_per_bundle": bundle_quantity,
        "quantity": total_units,
        "x": drop_x,
        "z": drop_z,
        "y": drop_y,
        "location_name": location_name,
        "unit_price": unit_price,
        "price": total_price,
        "created_at": time.time(),
        "status": "queued",
    })
    _write_config(DAYZ_SPAWN_QUEUE_FILE, queue)

    embed = discord.Embed(
        title=str(settings.get("purchase_title", "🛒 DayZ Purchase Queued"))[:256],
        description=(
            f"**{item.get('display_name', item_key)}**\n"
            f"Bundles: **{quantity}** • Total items: **{total_units}**"
        ),
        colour=0xD5A248,
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(name="Total", value=f"${total_price:,}", inline=True)
    embed.add_field(name="Drop point", value=location_name, inline=True)
    embed.add_field(
        name="Coordinates",
        value=f"X **{drop_x:.1f}** • Z **{drop_z:.1f}** • Y **{drop_y:.1f}**",
        inline=False,
    )

    image_url = str(item.get("image_url", "")).strip()
    if image_url:
        embed.set_thumbnail(url=image_url)

    embed.set_footer(text=f"Delivery request: {request_id}")
    await interaction.response.send_message(embed=embed)


@tree.command(
    name="buy",
    description="Buy a DayZ shop item"
)
@app_commands.describe(
    item="DayZ shop item key",
    quantity="How many bundles to buy",
    x="Drop X coordinate when custom locations are enabled",
    z="Drop Z coordinate when custom locations are enabled",
    y="Drop Y/height coordinate; normally 0"
)
async def dayz_buy_alias(
    interaction: discord.Interaction,
    item: str,
    quantity: app_commands.Range[int, 1, 100] = 1,
    x: float | None = None,
    z: float | None = None,
    y: float = 0.0
):
    await dz_buy.callback(
        interaction,
        item_key=item,
        quantity=quantity,
        x=x,
        z=z,
        y=y
    )


tree.add_command(dz_group)

async def _publish_deadside_leaderboard(guild_id, config, stats_root, force=False):
    if not config.get("leaderboard_enabled", True):
        return
    channel = _find_text_channel(config.get("leaderboard_channel"))
    if not channel:
        return
    server = stats_root["servers"].setdefault(str(guild_id), {"players": {}, "leaderboard_message_id": "", "last_leaderboard": 0})
    interval = max(60, min(int(config.get("leaderboard_interval", 300) or 300), 86400))
    now = time.time()
    if not force and now - float(server.get("last_leaderboard", 0) or 0) < interval:
        return
    limit = max(3, min(int(config.get("leaderboard_limit", 10) or 10), 25))
    players = server.get("players", {})
    ranked = sorted(players.items(), key=lambda item: (-int(item[1].get("kills", 0)), int(item[1].get("deaths", 0)), item[0].casefold()))[:limit]
    lines = []
    for index, (name, data) in enumerate(ranked, 1):
        kills = int(data.get("kills", 0)); deaths = int(data.get("deaths", 0))
        kd = kills / max(1, deaths)
        lines.append(f"**{index}. {discord.utils.escape_markdown(name)}** — {kills} kills • {deaths} deaths • {kd:.2f} K/D")
    if not lines:
        lines = ["No kills have been recorded yet."]
    embed = discord.Embed(
        title=str(config.get("leaderboard_title", "🏆 Deadside Leaderboard"))[:256],
        description="\n".join(lines)[:4096],
        colour=parse_colour(config.get("embed_color", "991111")),
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_footer(text=str(config.get("server_name", "Deadside Server"))[:2048])
    message = None
    message_id = str(server.get("leaderboard_message_id", ""))
    if message_id.isdigit():
        try:
            message = await channel.fetch_message(int(message_id))
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            message = None
    if message:
        await message.edit(embed=embed)
    else:
        message = await channel.send(embed=embed)
        server["leaderboard_message_id"] = str(message.id)
    server["last_leaderboard"] = now


async def _post_deadside_event(config, event):
    channel = _find_text_channel(config.get("killfeed_channel"))
    if not channel:
        return
    killer = event["killer"]
    victim = event["victim"]
    if not config.get("show_suicides", True) and killer.lower() == victim.lower():
        return
    colour = parse_colour(config.get("embed_color", "991111"))
    title = str(config.get("embed_title", "☠️ Deadside Killfeed"))[:256]
    embed = discord.Embed(title=title, colour=colour, timestamp=datetime.now(timezone.utc))
    embed.description = f"**{discord.utils.escape_markdown(killer)}** eliminated **{discord.utils.escape_markdown(victim)}**"
    if config.get("show_weapon", True) and event.get("weapon"):
        embed.add_field(name="Weapon", value=str(event["weapon"])[:1024], inline=True)
    if config.get("show_distance", True) and event.get("distance"):
        distance = str(event["distance"])
        if not distance.lower().endswith("m"):
            distance += " m"
        embed.add_field(name="Distance", value=distance[:1024], inline=True)
    if config.get("show_headshots", True) and event.get("headshot"):
        embed.add_field(name="Headshot", value="Yes 🎯", inline=True)
    server_name = str(config.get("server_name", "Deadside Server"))
    footer = str(config.get("embed_footer") or server_name)
    embed.set_footer(text=footer[:2048])
    thumbnail = str(config.get("embed_thumbnail", "")).strip()
    if thumbnail:
        embed.set_thumbnail(url=thumbnail)
    await channel.send(embed=embed)


@tasks.loop(seconds=30)
async def deadside_killfeed_loop():
    servers = _deadside_servers()
    state = _deadside_state()
    stats_root = _deadside_stats()
    changed = False
    stats_changed = False
    now = time.time()
    for guild_id, config in servers.items():
        if not isinstance(config, dict) or not config.get("enabled"):
            continue
        interval = max(30, min(int(config.get("poll_interval", 60) or 60), 900))
        guild_state = state["seen"].setdefault(str(guild_id), {"ids": [], "admin_ids": [], "last_poll": 0})
        if now - float(guild_state.get("last_poll", 0)) < interval:
            continue
        guild_state["last_poll"] = now
        changed = True
        try:
            raw = await asyncio.to_thread(_deadside_fetch_sync, config)
            events = _deadside_parse_events(raw, config)
            seen = set(guild_state.get("ids", []))
            new_events = [event for event in events if event["id"] not in seen]
            # On first connection, remember the existing history without flooding Discord.
            if not seen and events:
                new_events = []
            for event in new_events[-25:]:
                await _post_deadside_event(config, event)
                _update_deadside_stats(stats_root, guild_id, event)
                await _process_deadside_rewards(
                    guild_id,
                    config,
                    event,
                    stats_root
                )
                stats_changed = True
            await _publish_deadside_leaderboard(guild_id, config, stats_root)
            guild_state["ids"] = [event["id"] for event in events[-500:]]

            if config.get("admin_logs_enabled") and str(config.get("admin_logs_directory", "")).strip():
                admin_raw = await asyncio.to_thread(_deadside_fetch_admin_sync, config)
                admin_events = _deadside_parse_admin_events(admin_raw)
                admin_seen = set(guild_state.get("admin_ids", []))
                new_admin_events = [item for item in admin_events if item["id"] not in admin_seen]
                if not admin_seen and admin_events:
                    new_admin_events = []
                for admin_event in new_admin_events[-25:]:
                    await _post_deadside_admin_event(config, admin_event)
                guild_state["admin_ids"] = [item["id"] for item in admin_events[-500:]]

            guild_state.pop("last_error", None)
        except Exception as error:
            guild_state["last_error"] = str(error)[:500]
            print(f"Deadside poll error for guild {guild_id}: {error}")
    if changed:
        _write_config(DEADSIDE_STATE_FILE, state)
    if stats_changed or changed:
        _write_config(DEADSIDE_STATS_FILE, stats_root)


@deadside_killfeed_loop.before_loop
async def before_deadside_killfeed_loop():
    await bot.wait_until_ready()


async def apply_dashboard_feature(feature):
    if feature == "dayz":
        servers = _dz_servers()
        enabled = [cfg for cfg in servers.values() if isinstance(cfg, dict) and cfg.get("enabled")]
        for config in enabled:
            await asyncio.to_thread(_dz_test_nitrado, config)
            await asyncio.to_thread(_dz_fetch_log, config)
        if enabled and not dayz_log_loop.is_running():
            dayz_log_loop.start()
        return {"message": f"DayZ configured for {len(enabled)} server(s)"}

    if feature == "deadside":
        servers = _deadside_servers()
        enabled = [cfg for cfg in servers.values() if isinstance(cfg, dict) and cfg.get("enabled")]
        for config in enabled:
            if not _find_text_channel(config.get("killfeed_channel")):
                raise RuntimeError("Choose a valid Deadside killfeed channel.")
            if config.get("leaderboard_enabled", True) and not _find_text_channel(config.get("leaderboard_channel")):
                raise RuntimeError("Choose a valid Deadside leaderboard channel or disable leaderboards.")
            protocol = str(config.get("protocol") or config.get("connection_method") or "ftp").lower()
            if protocol in {"ftp", "ftps", "sftp"}:
                required = ("host", "username", "password")
                missing = [field for field in required if not str(config.get(field, "")).strip()]
                if missing:
                    raise RuntimeError(f"Deadside {protocol.upper()} connection is missing: {', '.join(missing)}")
                if not (_deadside_log_directory(config)):
                    raise RuntimeError("Enter a Deadside log path or death logs directory.")
            elif protocol in {"http", "https"}:
                if not str(config.get("feed_url", "")).startswith(("http://", "https://")):
                    raise RuntimeError("Enter a valid HTTP(S) Deadside log feed URL.")
            else:
                raise RuntimeError("Choose FTP, FTPS, SFTP or HTTP(S) as the protocol.")
            # Validate connection now so dashboard reports configuration errors immediately.
            raw = await asyncio.to_thread(_deadside_fetch_sync, config)
            _deadside_parse_events(raw, config)
        if enabled and not deadside_killfeed_loop.is_running():
            deadside_killfeed_loop.start()
        return {"message": f"Deadside killfeed configured for {len(enabled)} server(s)"}

    if feature == "rules":
        data = _read_config(RULES_FILE, {"menu": {}, "sections": {}})
        menu = data.setdefault("menu", {})
        if not data.get("sections"):
            raise RuntimeError("Add at least one rules section first.")
        channel = _find_text_channel(menu.get("channel_id"))
        if not channel:
            raise RuntimeError("Choose a valid rules channel.")
        embed = discord.Embed(
            title=menu.get("title", "🏴‍☠️ Pirates Server Rules"),
            description=menu.get("description", "Choose a rules section below."),
            colour=parse_colour(menu.get("color", "991111"))
        )
        if menu.get("thumbnail_url"): embed.set_thumbnail(url=menu["thumbnail_url"])
        if menu.get("image_url"): embed.set_image(url=menu["image_url"])
        if menu.get("footer"): embed.set_footer(text=menu["footer"])
        await _send_or_edit(channel, menu, "message_id", embed=embed, view=RulesMenuView())
        _write_config(RULES_FILE, data)
        return {"message": f"Rules menu updated in #{channel.name}"}

    if feature == "embeds":
        data = _read_config(EMBED_FILE, {})
        channel = _find_text_channel(data.get("channel_id"))
        if not channel: raise RuntimeError("Choose a valid embed channel.")
        embed = discord.Embed(
            title=data.get("title") or None,
            description=data.get("description") or None,
            colour=parse_colour(data.get("color", "ff0000"))
        )
        if data.get("thumbnail"): embed.set_thumbnail(url=data["thumbnail"])
        if data.get("image"): embed.set_image(url=data["image"])
        if data.get("footer"): embed.set_footer(text=data["footer"])
        await _send_or_edit(channel, data, "message_id", embed=embed)
        _write_config(EMBED_FILE, data)
        return {"message": f"Embed updated in #{channel.name}"}

    if feature == "tickets":
        data = load_ticket_settings()

        if not data.get("enabled", True):
            raise RuntimeError(
                "The ticket system is currently disabled."
            )

        channel = _find_text_channel(
            data.get("ticket_channel")
        )

        if not channel:
            raise RuntimeError(
                "Choose a valid ticket panel channel."
            )

        enabled_options = active_ticket_options()

        if not enabled_options:
            raise RuntimeError(
                "Create at least one enabled ticket option."
            )

        if len(enabled_options) > 25:
            raise RuntimeError(
                "Discord allows a maximum of 25 ticket options."
            )

        panel = data.get("panel", {})

        embed = discord.Embed(
            title=panel.get(
                "title",
                "🎟 Open a Ticket"
            ),
            description=panel.get(
                "description",
                "Select the type of ticket you want to open."
            ),
            colour=parse_colour(
                panel.get("color", "991111")
            )
        )

        footer = str(
            panel.get("footer", "")
        ).strip()

        image_url = str(
            panel.get("image_url", "")
        ).strip()

        thumbnail_url = str(
            panel.get("thumbnail_url", "")
        ).strip()

        if footer:
            embed.set_footer(text=footer)

        if image_url:
            embed.set_image(url=image_url)

        if thumbnail_url:
            embed.set_thumbnail(url=thumbnail_url)

        selection_type = str(
            data.get("selection_type", "buttons")
        ).lower()

        if selection_type == "dropdown":
            ticket_view = TicketDropdownView()
        else:
            ticket_view = TicketButtonsView()

        await _send_or_edit(
            channel,
            data,
            "panel_message_id",
            embed=embed,
            view=ticket_view
        )

        data["guild_id"] = str(channel.guild.id)
        data["option_count"] = len(
            data.get("options", [])
        )

        save_ticket_settings(data)

        return {
            "message": (
                f"Ticket panel updated in "
                f"#{channel.name}"
            )
        }

    if feature == "reaction_roles":
        data = _read_config(REACTION_ROLE_FILE, {"roles": []})
        channel = _find_text_channel(data.get("channel_id"))
        if not channel: raise RuntimeError("Choose a valid reaction-role channel.")
        lines = ["React below to receive a role:"]
        for item in data.get("roles", []):
            role = channel.guild.get_role(int(item.get("role_id"))) if str(item.get("role_id", "")).isdigit() else None
            lines.append(f"{item.get('emoji', '🎭')} — {role.mention if role else 'Configured role'}")
        message = await _send_or_edit(channel, data, "message_id", content="\n".join(lines))
        for item in data.get("roles", []):
            if item.get("emoji"):
                try: await message.add_reaction(item["emoji"])
                except discord.HTTPException: pass
        data["guild_id"] = str(channel.guild.id)
        _write_config(REACTION_ROLE_FILE, data)
        return {"message": f"Reaction roles updated in #{channel.name}"}

    if feature == "welcome":
        data = _read_config(WELCOME_FILE, {})
        channel = _find_text_channel(data.get("channel") or data.get("channel_id"))
        if not channel: raise RuntimeError("Choose a valid welcome channel.")
        data["guild_id"] = str(channel.guild.id)
        preview = str(data.get("message", "Welcome {user} to {server}!"))
        preview = preview.replace("{user}", bot.user.mention).replace("{server}", channel.guild.name)
        embed = discord.Embed(title="👋 Welcome preview", description=preview, colour=discord.Color.red())
        image = data.get("banner_url") or data.get("image_url")
        if image: embed.set_image(url=image)
        await _send_or_edit(channel, data, "preview_message_id", embed=embed)
        _write_config(WELCOME_FILE, data)
        return {"message": f"Welcome settings applied in #{channel.name}"}

    if feature == "moderation":
        data = _read_config(MODERATION_FILE, {})
        channel = _find_text_channel(data.get("log_channel"))
        if not channel: raise RuntimeError("Choose a valid moderation log channel.")
        automod = data.get("automod", {})
        description = (
            f"**Enabled:** {data.get('enabled', False)}\n"
            f"**Anti-spam:** {automod.get('anti_spam', False)}\n"
            f"**Anti-links:** {automod.get('anti_links', False)}\n"
            f"**Word filter:** {automod.get('word_filter', False)}"
        )
        embed = discord.Embed(title="🛡 Moderation settings updated", description=description, colour=discord.Color.red())
        await _send_or_edit(channel, data, "status_message_id", embed=embed)
        data["guild_id"] = str(channel.guild.id)
        _write_config(MODERATION_FILE, data)
        return {"message": f"Moderation settings applied for {channel.guild.name}"}

    if feature == "polls":
        data = _read_config(POLL_FILE, {})
        channel = _find_text_channel(data.get("channel_id"))
        if not channel:
            raise RuntimeError("Choose a valid poll channel.")

        question = str(data.get("question", "")).strip()
        if not question:
            raise RuntimeError("Enter a poll question.")

        colour = parse_colour(data.get("color", "5865F2"), 0x5865F2)
        embed = discord.Embed(
            title=data.get("title") or "📊 Poll",
            description=f"**{question}**",
            colour=colour
        )
        embed.add_field(name="✅ Yes", value="0", inline=True)
        embed.add_field(name="❌ No", value="0", inline=True)
        if data.get("footer"):
            embed.set_footer(text=str(data["footer"]))

        # A new poll is intentionally posted each time so old votes are not erased.
        message = await channel.send(embed=embed, view=PollView(question))
        data["message_id"] = str(message.id)
        data["guild_id"] = str(channel.guild.id)
        _write_config(POLL_FILE, data)
        return {"message": f"Poll published in #{channel.name}", "message_id": str(message.id)}

    if feature == "giveaways":
        data = _read_config(GIVEAWAY_FILE, {})
        channel = _find_text_channel(data.get("channel_id"))
        if not channel:
            raise RuntimeError("Choose a valid giveaway channel.")

        prize = str(data.get("prize", "")).strip()
        if not prize:
            raise RuntimeError("Enter a giveaway prize.")

        try:
            duration = max(10, int(data.get("duration_seconds", 3600)))
        except (TypeError, ValueError):
            duration = 3600

        colour = parse_colour(data.get("color", "F1C40F"), 0xF1C40F)
        embed = discord.Embed(
            title=data.get("title") or "🎉 Giveaway",
            description=(
                f"**Prize:** {prize}\n"
                f"**Winners:** {max(1, int(data.get('winner_count', 1)))}\n"
                f"**Ends in:** {duration} seconds\n\n"
                "Press the button below to enter!"
            ),
            colour=colour
        )
        if data.get("image_url"):
            embed.set_image(url=str(data["image_url"]))
        if data.get("footer"):
            embed.set_footer(text=str(data["footer"]))

        view = GiveawayView(
            duration,
            prize,
            winner_count=max(1, int(data.get("winner_count", 1)))
        )
        message = await channel.send(embed=embed, view=view)
        view.message = message
        data["message_id"] = str(message.id)
        data["guild_id"] = str(channel.guild.id)
        _write_config(GIVEAWAY_FILE, data)
        return {"message": f"Giveaway started in #{channel.name}", "message_id": str(message.id)}

    if feature == "settings":
        data = _read_config(DASHBOARD_FILE, {})
        status_text = str(data.get("status", "Pirates Bot"))
        await bot.change_presence(activity=discord.Game(name=status_text))
        return {"message": "Bot presence updated"}

    if feature == "economy":
        return {"message": "Economy settings saved and will be used by configured commands"}

    return {"message": "Settings applied"}




# ------------------- PIRATES BOT HELP SETUP -------------------
PIRATES_HELP_IMAGE = os.path.join(
    BASE_DIR,
    "assets",
    "help",
    "pirates_bot_help.png"
)

PIRATES_DASHBOARD_URL = (
    "https://amusing-inspiration-production-eab1.up.railway.app/"
)


class PiratesHelpView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

        self.add_item(
            discord.ui.Button(
                label="Open Pirates Bot Dashboard",
                emoji="🖥️",
                style=discord.ButtonStyle.link,
                url=PIRATES_DASHBOARD_URL,
            )
        )


help_group = app_commands.Group(
    name="help",
    description="Pirates Bot help and setup tools"
)


@help_group.command(
    name="setup",
    description="Admin: Post the Pirates Bot help guide"
)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(
    channel="Channel to post the help guide in; leave blank for this channel"
)
async def help_setup(
    interaction: discord.Interaction,
    channel: discord.TextChannel | None = None
):
    if interaction.guild is None:
        return await interaction.response.send_message(
            "❌ Use this command inside a Discord server.",
            ephemeral=True,
        )

    target = channel or interaction.channel

    if not isinstance(target, discord.TextChannel):
        return await interaction.response.send_message(
            "❌ Choose a normal Discord text channel.",
            ephemeral=True,
        )

    permissions = target.permissions_for(interaction.guild.me)
    if not permissions.view_channel or not permissions.send_messages:
        return await interaction.response.send_message(
            f"❌ I cannot send messages in {target.mention}.",
            ephemeral=True,
        )

    if not os.path.isfile(PIRATES_HELP_IMAGE):
        return await interaction.response.send_message(
            "❌ The Pirates Bot help image is missing from "
            "`assets/help/pirates_bot_help.png`.",
            ephemeral=True,
        )

    await interaction.response.defer(ephemeral=True)

    image_file = discord.File(
        PIRATES_HELP_IMAGE,
        filename="pirates_bot_help.png"
    )

    embed = discord.Embed(
        title="☠️ Pirates Bot Help Centre",
        description=(
            "Everything you need to get started with Pirates Bot.\n\n"
            "Use the guide below for commands, game integrations and "
            "dashboard setup."
        ),
        colour=0xB8860B,
    )
    embed.set_image(url="attachment://pirates_bot_help.png")
    embed.set_footer(text="Pirates Bot • Rule the server. Command the seas.")

    message = await target.send(
        embed=embed,
        file=image_file,
        view=PiratesHelpView(),
    )

    await interaction.followup.send(
        f"✅ Help guide posted in {target.mention}.\n"
        f"[Jump to message]({message.jump_url})",
        ephemeral=True,
    )


tree.add_command(help_group)


    # ------------------- READY -------------------
@bot.event
async def on_ready():
    if not getattr(
        bot,
        "_persistent_views_registered",
        False
    ):
        bot.add_view(RulesMenuView())
        bot.add_view(CloseTicketView())

        ticket_data = load_ticket_settings()

        selection_type = str(
            ticket_data.get(
                "selection_type",
                "buttons"
            )
        ).lower()

        enabled_options = active_ticket_options()

        if enabled_options:
            if selection_type == "dropdown":
                bot.add_view(TicketDropdownView())
            else:
                bot.add_view(TicketButtonsView())

        bot._persistent_views_registered = True

    await tree.sync()

    if not auto_announcement_loop.is_running():
        auto_announcement_loop.start()
        
    if not reminder_loop.is_running():
        reminder_loop.start()

    if not deadside_killfeed_loop.is_running():
        deadside_killfeed_loop.start()

    if not dayz_log_loop.is_running():
        dayz_log_loop.start()

    print(f"✅ Logged in as {bot.user}")
    print(
        f"✅ Connected to "
        f"{len(bot.guilds)} servers"
    )

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise RuntimeError(
        "DISCORD_TOKEN is missing from your .env file."
    )

print("STARTING DISCORD BOT...")

Thread(target=run_web, daemon=True).start()
bot.run(TOKEN)