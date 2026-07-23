import discord
from discord.ext import commands
from discord import app_commands
import json
import random
from datetime import datetime, timedelta
import asyncio
import time
from math import floor
from dotenv import load_dotenv
load_dotenv()

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
# ------------------- GIVEAWAY VIEW -------------------
class GiveawayView(discord.ui.View):
    def __init__(self, duration: int, prize: str, author: discord.Member):
        super().__init__(timeout=duration)
        self.entries = []
        self.prize = prize
        self.author = author
        self.message = None  # will be set after sending

    @discord.ui.button(label="Enter Giveaway 🎉", style=discord.ButtonStyle.green)
    async def enter(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user in self.entries:
            await interaction.response.send_message("❌ You already entered!", ephemeral=True)
        else:
            self.entries.append(interaction.user)
            await interaction.response.send_message("✅ You entered the giveaway!", ephemeral=True)

    async def on_timeout(self):
        if not self.message:
            return
        if not self.entries:
            await self.message.edit(content=f"🎉 Giveaway for **{self.prize}** ended! No entries 😢", view=None)
            return
        winner = random.choice(self.entries)
        await self.message.edit(content=f"🎉 Giveaway for **{self.prize}** ended! Winner: {winner.mention}", view=None)
        try:
            await winner.send(f"🎉 Congrats! You won the giveaway for **{self.prize}** in {self.message.guild.name}!")
        except:
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

    @discord.ui.button(label="✅ Yes", style=discord.ButtonStyle.green)
    async def yes_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in self.votes["yes"]:
            return await interaction.response.send_message("You already voted ✅", ephemeral=True)
        if interaction.user.id in self.votes["no"]:
            self.votes["no"].remove(interaction.user.id)
        self.votes["yes"].append(interaction.user.id)
        await self.update_message(interaction)

    @discord.ui.button(label="❌ No", style=discord.ButtonStyle.red)
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
    
    # ================== JOB SYSTEM ==================

JOB_FILE = "jobs.json"
ACTIVITY_FILE = "activity.json"

# Job definitions
JOBS = {
    "doctor": {
        "name": "Doctor",
        "min": 300,
        "max": 600,
        "risk": 0.0
    },
    "policeman": {
        "name": "Policeman",
        "min": 250,
        "max": 500,
        "risk": 0.0
    },
    "crimeboss": {
        "name": "Crime Boss",
        "min": 500,
        "max": 900,
        "risk": 0.35  # 35% chance to lose money
    }
}

def level_requirement(level: int):
    return level * 100

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

# ---------- ACTIVITY TRACKING ----------
@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    activity = load_activity()
    uid = str(message.author.id)

    activity.setdefault(uid, {"messages": 0})
    activity[uid]["messages"] += 1

    save_activity(activity)
    await bot.process_commands(message)

# ---------- /job ----------
@tree.command(name="job", description="Choose a job")
@app_commands.describe(job="doctor / policeman / crimeboss")
async def job(interaction: discord.Interaction, job: str):
    job = job.lower()
    if job not in JOBS:
        return await interaction.response.send_message("❌ Invalid job choice.")

    jobs = load_jobs()
    uid = str(interaction.user.id)

    jobs[uid] = {
        "job": job,
        "level": 1,
        "xp": 0,
        "last_daily": None
    }

    save_jobs(jobs)
    await interaction.response.send_message(f"💼 You are now a **{JOBS[job]['name']}**!")


# -------- Your existing imports and data functions --------
# load_jobs(), save_jobs(), update_bank(), JOBS, JOB_ROLES, level_requirement()

# -------- /dailyjob command --------
@tree.command(name="dailyjob", description="Collect your daily salary")
async def dailyjob(interaction: discord.Interaction):
    # Defer response to prevent "interaction failed"
    await interaction.response.defer()

    uid = str(interaction.user.id)
    jobs = load_jobs()

    # Check if user has a job
    if uid not in jobs:
        return await interaction.followup.send("❌ You don't have a job.")

    data = jobs[uid]
    today = datetime.now().strftime("%Y-%m-%d")

    # Check daily cooldown
    if data.get("last_daily") == today:
        return await interaction.followup.send("⏳ You have already claimed your daily salary today.")

    job = JOBS.get(data["job"])
    if not job:
        return await interaction.followup.send("❌ Your job data is invalid.")

    # Calculate salary
    salary = random.randint(job["min"], job["max"]) + (data.get("level", 1) * 50)

    # Determine success/failure based on job risk
    if job.get("risk", 0) > 0 and random.random() < job["risk"]:
        update_bank(interaction.user.id, -salary)
        msg = f"💥 Job failed! You lost **${salary}**."
    else:
        update_bank(interaction.user.id, salary)
        msg = f"💰 You earned **${salary}** from your job today!"

    # Add XP and handle leveling
    data["xp"] = data.get("xp", 0) + random.randint(25, 50)
    leveled = False

    while data["xp"] >= level_requirement(data.get("level", 1)):
        data["xp"] -= level_requirement(data.get("level", 1))
        data["level"] = data.get("level", 1) + 1
        leveled = True

        # Handle promotion role assignment
        role_name = JOB_ROLES.get(data["job"], {}).get(data["level"])
        if role_name and interaction.guild:
            role = discord.utils.get(interaction.guild.roles, name=role_name)
            if role:
                try:
                    await interaction.user.add_roles(role)
                except discord.Forbidden:
                    await interaction.followup.send(f"⚠ Could not assign role `{role_name}` due to permissions.")

        # Send promotion embed
        if interaction.guild:
            embed = discord.Embed(
                title="💸 Promotion!",
                description=f"{interaction.user.mention} has been promoted to **Level {data['level']}**!",
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed)

    # Update last_daily and save
    data["last_daily"] = today
    save_jobs(jobs)

    # Send main salary message
    await interaction.followup.send(msg)
# ---------- /jobinfo ----------
@tree.command(name="jobinfo", description="View your job progress")
async def jobinfo(interaction: discord.Interaction):
    jobs = load_jobs()
    activity = load_activity()
    uid = str(interaction.user.id)

    if uid not in jobs:
        return await interaction.response.send_message("❌ You don't have a job.")

    data = jobs[uid]
    job = JOBS[data["job"]]
    xp_needed = level_requirement(data["level"])
    progress = min(int((data["xp"] / xp_needed) * 10), 10)
    bar = "🟩" * progress + "⬜" * (10 - progress)

    embed = discord.Embed(title="💼 Job Info", color=discord.Color.blue())
    embed.add_field(name="Job", value=job["name"], inline=True)
    embed.add_field(name="Level", value=data["level"], inline=True)
    embed.add_field(name="XP", value=f"{data['xp']} / {xp_needed}", inline=False)
    embed.add_field(name="Progress", value=bar, inline=False)
    embed.add_field(
        name="Salary",
        value=f"${job['min']} - ${job['max']} (+50 per level)",
        inline=True
    )
    embed.add_field(
        name="Risk",
        value=f"{int(job.get('risk',0)*100)}%",
        inline=True
    )
    embed.add_field(
        name="Activity",
        value=f"💬 Messages: {activity.get(uid, {}).get('messages', 0)}",
        inline=False
    )
    embed.add_field(name="Last Daily Claim", value=data.get("last_daily", "Never"), inline=False)

    await interaction.response.send_message(embed=embed)


# ---------- /jobleaderboard ----------
@tree.command(name="jobleaderboard", description="Top job workers")
async def jobleaderboard(interaction: discord.Interaction):
    jobs = load_jobs()

    ranked = sorted(jobs.items(), key=lambda x: x[1]["level"], reverse=True)[:10]

    embed = discord.Embed(title="🏆 Job Leaderboard", color=discord.Color.gold())

    for i, (uid, data) in enumerate(ranked, start=1):
        member = interaction.guild.get_member(int(uid))
        name = member.display_name if member else "Unknown"

        embed.add_field(
            name=f"#{i} {name}",
            value=f"{JOBS[data['job']]['name']} — Level {data['level']}",
            inline=False
        )

    await interaction.response.send_message(embed=embed)

# ---------- ADMIN CONFIG ----------
@tree.command(name="setjobpay", description="Admin: Set job pay & risk")
@app_commands.checks.has_permissions(administrator=True)
async def setjobpay(
    interaction: discord.Interaction,
    job: str,
    min_pay: int,
    max_pay: int,
    risk: float = 0.0
):
    job = job.lower()
    if job not in JOBS:
        return await interaction.response.send_message("❌ Invalid job.")

    JOBS[job]["min"] = min_pay
    JOBS[job]["max"] = max_pay
    JOBS[job]["risk"] = risk

    await interaction.response.send_message("✅ Job settings updated.")

    # ------------------- TICKET SYSTEM -------------------
class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎫 Create Ticket", style=discord.ButtonStyle.green)
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        user = interaction.user

        category = discord.utils.get(guild.categories, name=TICKET_CATEGORY_NAME)
        if category is None:
            category = await guild.create_category(TICKET_CATEGORY_NAME)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(view_channel=True)
        }

        for role_name in STAFF_ROLES:
            role = discord.utils.get(guild.roles, name=role_name)
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        channel = await guild.create_text_channel(
            name=f"ticket-{user.name}",
            category=category,
            overwrites=overwrites
        )

        await channel.send(
            f"{user.mention} Welcome! Describe your issue.\nPress 🔒 to close.",
            view=CloseView()
        )

        await interaction.response.send_message(
            f"✅ Ticket created: {channel.mention}",
            ephemeral=True
        )

class CloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 Close Ticket", style=discord.ButtonStyle.red)
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.channel.delete()

@tree.command(name="ticketpanel", description="Send ticket panel")
@app_commands.checks.has_permissions(administrator=True)
async def ticketpanel(interaction: discord.Interaction):
    await interaction.response.send_message(
        "Click below to create a ticket:",
        view=TicketView()
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
@is_staff()
@app_commands.checks.cooldown(1, 600)
async def work(interaction: discord.Interaction):
    earn = random.randint(10, 100)
    update_bank(interaction.user.id, earn)
    await interaction.response.send_message(f"🛠 You earned ${earn}")

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

@bot.event
async def on_raw_reaction_add(payload):
    roles = get_reaction_roles().get(str(payload.guild_id), {})
    role_id = roles.get(str(payload.message_id), {}).get(str(payload.emoji))
    if not role_id:
        return
    guild = bot.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)
    role = guild.get_role(role_id)
    if role:
        await member.add_roles(role)

@bot.event
async def on_raw_reaction_remove(payload):
    roles = get_reaction_roles().get(str(payload.guild_id), {})
    role_id = roles.get(str(payload.message_id), {}).get(str(payload.emoji))
    if not role_id:
        return
    guild = bot.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)
    role = guild.get_role(role_id)
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
    welcome_data = get_welcome_settings().get(str(member.guild.id))
    if welcome_data:
        channel = member.guild.get_channel(welcome_data["channel"])
        if channel:
            content = welcome_data["message"].replace("{user}", member.mention).replace("{server}", member.guild.name)
            if welcome_data.get("image"):
                embed = discord.Embed(description=content, color=discord.Color.green())
                embed.set_image(url=welcome_data["image"])
                await channel.send(embed=embed)
            else:
                await channel.send(content)

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
    # ------------------- READY -------------------
@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ Logged in as {bot.user}")

import os

bot.run(os.getenv("DISCORD_TOKEN"))