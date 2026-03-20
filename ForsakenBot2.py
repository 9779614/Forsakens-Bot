import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from datetime import datetime
from openai import OpenAI

# -----------------------
# ENV / CONFIG
# -----------------------

TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

DATA_FILE = "storage.json"
CONFIG_FILE = "config.json"

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# -----------------------
# FILE HANDLING
# -----------------------

def load_json(file):
    if not os.path.exists(file):
        return {}
    with open(file, "r") as f:
        return json.load(f)

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=4)

storage = load_json(DATA_FILE)
config = load_json(CONFIG_FILE)

# -----------------------
# AMMO MAP
# -----------------------

ammo_map = {
    "556": "5.56x45",
    "545": "5.45x39",
    "762": "7.62x39",
    "308": ".308",
    "9mm": "9x19",
    "380": ".380 ACP",
    "12g": "12 Gauge",
    "22": ".22 LR"
}

def normalize(item):
    return ammo_map.get(item.lower(), item.lower())

# -----------------------
# ARMOR TIERS
# -----------------------

armor_map = {
    "t0": "No armor",
    "t1": "Light clothing",
    "t2": "Light protection",
    "t3": "Stab vest",
    "t4": "Plate carrier",
    "t5": "Military carrier",
    "t6": "Heavy armor"
}

# -----------------------
# EMBED
# -----------------------

def build_embed():
    embed = discord.Embed(
        title="📦 Forsaken Storage",
        color=discord.Color.orange()
    )

    if not storage:
        embed.description = "Empty"
    else:
        embed.description = "\n".join(
            [f"**{i}** : {a}" for i, a in sorted(storage.items())]
        )

    return embed

async def update_embed():
    try:
        channel = bot.get_channel(config.get("channel_id"))
        message = await channel.fetch_message(config.get("message_id"))
        await message.edit(embed=build_embed())
    except:
        pass

# -----------------------
# LOGGING
# -----------------------

async def log_action(action, user, item, amount, total):

    log_id = config.get("log_channel_id")
    if not log_id:
        return

    channel = bot.get_channel(log_id)

    embed = discord.Embed(
        title="📦 Storage Log",
        color=discord.Color.blue(),
        timestamp=datetime.utcnow()
    )

    embed.add_field(name="Action", value=action)
    embed.add_field(name="Item", value=item)
    embed.add_field(name="Amount", value=amount)
    embed.add_field(name="Total", value=total)

    embed.set_footer(text=f"{user}")

    await channel.send(embed=embed)

# -----------------------
# READY
# -----------------------

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Logged in as {bot.user}")

# -----------------------
# SETUP
# -----------------------

@bot.tree.command(name="setupstorage")
async def setupstorage(interaction: discord.Interaction):

    await interaction.response.defer(ephemeral=True)

    msg = await interaction.channel.send(embed=build_embed())

    config["channel_id"] = interaction.channel.id
    config["message_id"] = msg.id

    save_json(CONFIG_FILE, config)

    await interaction.followup.send("Storage setup complete.", ephemeral=True)

@bot.tree.command(name="setlogchannel")
async def setlogchannel(interaction: discord.Interaction):

    config["log_channel_id"] = interaction.channel.id
    save_json(CONFIG_FILE, config)

    await interaction.response.send_message("Log channel set.", ephemeral=True)

# -----------------------
# CHECK
# -----------------------

def valid_channel(interaction):
    return interaction.channel.id == config.get("channel_id")

# -----------------------
# STORAGE COMMANDS
# -----------------------

@bot.tree.command(name="add")
async def add(interaction: discord.Interaction, amount: int, item: str):

    if not valid_channel(interaction):
        return await interaction.response.send_message("Wrong channel.", ephemeral=True)

    item = normalize(item)
    storage[item] = storage.get(item, 0) + amount

    save_json(DATA_FILE, storage)
    await update_embed()
    await log_action("Added", interaction.user, item, amount, storage[item])

    await interaction.response.send_message("Added.", ephemeral=True)

@bot.tree.command(name="remove")
async def remove(interaction: discord.Interaction, amount: int, item: str):

    if not valid_channel(interaction):
        return await interaction.response.send_message("Wrong channel.", ephemeral=True)

    item = normalize(item)

    if item not in storage:
        return await interaction.response.send_message("Not found.", ephemeral=True)

    storage[item] -= amount

    if storage[item] <= 0:
        del storage[item]
        total = 0
    else:
        total = storage[item]

    save_json(DATA_FILE, storage)
    await update_embed()
    await log_action("Removed", interaction.user, item, amount, total)

    await interaction.response.send_message("Removed.", ephemeral=True)

@bot.tree.command(name="search")
async def search(interaction: discord.Interaction, item: str):

    item = normalize(item)

    if item in storage:
        await interaction.response.send_message(f"{item}: {storage[item]}")
    else:
        await interaction.response.send_message("Not found.")

@bot.tree.command(name="lowstock")
async def lowstock(interaction: discord.Interaction, threshold: int = 50):

    low = [f"{i}: {a}" for i, a in storage.items() if a <= threshold]

    if not low:
        await interaction.response.send_message("No low stock.")
    else:
        await interaction.response.send_message("\n".join(low))

# -----------------------
# INJURY SYSTEM
# -----------------------

@bot.tree.command(name="injury")
async def injury(interaction: discord.Interaction, caliber: str, location: str, distance: int, armor: str = "t0"):

    await interaction.response.defer()

    if armor.lower() not in armor_map:
        return await interaction.followup.send("Use T0-T6 armor.")

    try:
        prompt = f"""
        Generate a realistic but survivable DayZ RP gunshot injury.

        Caliber: {caliber}
        Location: {location}
        Distance: {distance}
        Armor: {armor}

        Must include severity, effects, treatment.
        Keep concise.
        """

        response = client.responses.create(
            model="gpt-5-mini",
            input=prompt,
            max_output_tokens=200
        )

        result = response.output[0].content[0].text

        embed = discord.Embed(title="🩸 Injury Report", description=result, color=discord.Color.red())
        await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send(f"Error: {e}")

# -----------------------

bot.run(TOKEN)