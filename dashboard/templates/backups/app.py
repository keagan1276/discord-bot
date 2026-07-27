from flask import Flask, render_template, request, redirect, jsonify
import json
import os
import requests
from dotenv import load_dotenv


load_dotenv()


BOT_API_URL = os.getenv("BOT_API_URL", "http://127.0.0.1:10000").rstrip("/")

DASHBOARD_API_KEY = os.getenv(
    "DASHBOARD_API_KEY",
    ""
)


def bot_api_get(endpoint):

    try:
        response = requests.get(
            f"{BOT_API_URL}{endpoint}",
            headers={
                "X-Dashboard-Key": DASHBOARD_API_KEY
            },
            timeout=3
        )

        response.raise_for_status()

        return response.json()

    except requests.RequestException as error:
        print(f"Bot API error: {error}")
        return None


def bot_api_post(endpoint):
    try:
        response = requests.post(
            f"{BOT_API_URL}{endpoint}",
            headers={"X-Dashboard-Key": DASHBOARD_API_KEY},
            timeout=18
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as error:
        detail = ""
        if getattr(error, "response", None) is not None:
            try:
                detail = error.response.json().get("error", "")
            except ValueError:
                detail = error.response.text
        print(f"Bot apply error: {detail or error}")
        return {"ok": False, "error": detail or str(error)}


def apply_to_discord(feature):
    return bot_api_post(f"/api/dashboard/apply/{feature}")

BASE_FOLDER = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_FOLDER, "templates"),
    static_folder=os.path.join(BASE_FOLDER, "static")
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


@app.route("/api/guilds")
def dashboard_guilds():
    return jsonify(api_json("/api/guilds", []))


@app.route("/api/guild/<guild_id>/channels")
def dashboard_channels(guild_id):
    return jsonify(api_json(f"/api/guild/{guild_id}/channels", []))


@app.route("/api/guild/<guild_id>/roles")
def dashboard_roles(guild_id):
    return jsonify(api_json(f"/api/guild/{guild_id}/roles", []))


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


    if request.method == "POST":

        # Work
        economy["work"]["min_reward"] = int(request.form["work_min"])
        economy["work"]["max_reward"] = int(request.form["work_max"])
        economy["work"]["cooldown"] = int(request.form["work_cooldown"])


        # Crime
        economy["crime"]["success_chance"] = int(request.form["crime_chance"])
        economy["crime"]["min_reward"] = int(request.form["crime_min"])
        economy["crime"]["max_reward"] = int(request.form["crime_max"])
        economy["crime"]["fail_loss"] = int(request.form["crime_loss"])
        economy["crime"]["cooldown"] = int(request.form["crime_cooldown"])


        # Rob
        economy["rob"]["success_chance"] = int(request.form["rob_chance"])
        economy["rob"]["min_reward"] = int(request.form["rob_min"])
        economy["rob"]["max_reward"] = int(request.form["rob_max"])
        economy["rob"]["fail_loss"] = int(request.form["rob_loss"])
        economy["rob"]["cooldown"] = int(request.form["rob_cooldown"])


        # Blackjack
        economy["blackjack"]["min_bet"] = int(request.form["blackjack_min"])
        economy["blackjack"]["max_bet"] = int(request.form["blackjack_max"])
        economy["blackjack"]["cooldown"] = int(request.form["blackjack_cooldown"])


        # Roulette
        economy["roulette"]["min_bet"] = int(request.form["roulette_min"])
        economy["roulette"]["max_bet"] = int(request.form["roulette_max"])
        economy["roulette"]["cooldown"] = int(request.form["roulette_cooldown"])


        # Daily
        economy["daily"]["reward"] = int(request.form["daily_reward"])
        economy["daily"]["cooldown"] = int(request.form["daily_cooldown"])


        # Weekly
        economy["weekly"]["reward"] = int(request.form["weekly_reward"])
        economy["weekly"]["cooldown"] = int(request.form["weekly_cooldown"])


        # Bank
        economy["bank"]["max_storage"] = int(request.form["bank_storage"])
        economy["bank"]["interest_rate"] = int(request.form["bank_interest"])
        economy["bank"]["interest_cooldown"] = int(request.form["bank_interest_cooldown"])


        with open(ECONOMY_FILE, "w", encoding="utf-8") as file:
            json.dump(economy, file, indent=4)

        apply_to_discord("economy")


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

        apply_to_discord("welcome")


    return render_template(
        "welcome.html",
        welcome=welcome
    )
@app.route("/tickets", methods=["GET", "POST"])
def tickets():

    with open(TICKET_FILE, "r", encoding="utf-8") as file:
        ticket = json.load(file)


    if request.method == "POST":

        ticket["enabled"] = "enabled" in request.form

        ticket["category_id"] = request.form["category_id"]

        ticket["staff_role_id"] = request.form["staff_role_id"]

        ticket["ticket_channel"] = request.form["ticket_channel"]

        ticket["message"] = request.form["message"]


        ticket["button"]["enabled"] = "button_enabled" in request.form

        ticket["button"]["text"] = request.form["button_text"]


        ticket["settings"]["close_message"] = request.form["close_message"]

        ticket["settings"]["transcript"] = "transcript" in request.form

        ticket["settings"]["delete_after_close"] = "delete_after_close" in request.form



        with open(TICKET_FILE, "w", encoding="utf-8") as file:
            json.dump(ticket, file, indent=4)

        apply_to_discord("tickets")



    return render_template(
        "tickets.html",
        ticket=ticket
    )


@app.route("/moderation", methods=["GET", "POST"])
def moderation():

    with open(MODERATION_FILE, "r", encoding="utf-8") as file:
        moderation = json.load(file)


    if request.method == "POST":

        moderation["enabled"] = "enabled" in request.form

        moderation["log_channel"] = request.form["log_channel"]


        # Auto Moderation
        moderation["automod"]["enabled"] = "automod" in request.form

        moderation["automod"]["anti_spam"] = "anti_spam" in request.form

        moderation["automod"]["anti_links"] = "anti_links" in request.form

        moderation["automod"]["word_filter"] = "word_filter" in request.form



        # Warnings
        moderation["warnings"]["enabled"] = "warnings" in request.form

        moderation["warnings"]["max_warnings"] = int(
            request.form["max_warnings"]
        )



        # Punishments
        moderation["kick"]["enabled"] = "kick" in request.form

        moderation["ban"]["enabled"] = "ban" in request.form


        moderation["mute"]["enabled"] = "mute" in request.form

        moderation["mute"]["duration"] = int(
            request.form["mute_duration"]
        )



        with open(MODERATION_FILE, "w", encoding="utf-8") as file:
            json.dump(moderation, file, indent=4)

        apply_to_discord("moderation")



    return render_template(
        "moderation.html",
        moderation=moderation
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

        apply_to_discord("settings")


    return render_template(
    "settings.html",
    dashboard=dashboard
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

        apply_to_discord("embeds")


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

        apply_to_discord("reaction_roles")


    return render_template(
        "reaction_roles.html",
        roles=roles
    )
    
    
    
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

        apply_to_discord("rules")
        return redirect("/rules")

    return render_template(
        "rules.html",
        rules=rules_data
    )

if __name__ == "__main__":
    print("RUNNING FILE:", os.path.abspath(__file__))

    app.run(
        host="127.0.0.1",
        port=5050,
        debug=True,
        use_reloader=False
    )