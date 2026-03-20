import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from datetime import datetime
from openai import OpenAI

# =========================
# ENV
# =========================

TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

DATA_FILE = "storage.json"
CONFIG_FILE = "config.json"

# =========================
# BOT SETUP
# =========================

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# =========================
# FILE HANDLING
# =========================

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

# =========================
# AMMO NORMALIZATION
# =========================

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

# =========================
# ARMOR TIERS
# =========================

armor_map = {
    "t0": "No armor",
    "t1": "Light clothing",
    "t2": "Light protection",
    "t3": "Stab vest",
    "t4": "Plate carrier",
    "t5": "Military carrier",
    "t6": "Heavy armor"
}

# =========================
# STORAGE EMBED
# =========================

def build_storage_embed():
    embed = discord.Embed(
        title="📦 Forsaken Communal Storage",
        color=discord.Color.orange()
    )

    if not storage:
        embed.description = "Storage is empty."
    else:
        embed.description = "\n".join(
            [f"**{item}** : {amount}" for item, amount in sorted(storage.items())]
        )

    embed.set_footer(text="Live Storage System")

    return embed

async def update_storage_embed():
    try:
        channel = bot.get_channel(config.get("storage_channel_id"))
        message = await channel.fetch_message(config.get("storage_message_id"))
        await message.edit(embed=build_storage_embed())
    except:
        pass

# =========================
# LOGGING
# =========================

async def log_action(action, user, item, amount, total):

    log_channel_id = config.get("log_channel_id")
    if not log_channel_id:
        return

    channel = bot.get_channel(log_channel_id)
    if not channel:
        return

    embed = discord.Embed(
        title="📦 Storage Log",
        color=discord.Color.blue(),
        timestamp=datetime.utcnow()
    )

    embed.add_field(name="Action", value=action)
    embed.add_field(name="Item", value=item)
    embed.add_field(name="Amount", value=amount)
    embed.add_field(name="Total", value=total)

    embed.set_footer(text=f"{user} | {user.id}")

    await channel.send(embed=embed)

# =========================
# READY
# =========================

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Bot ready: {bot.user}")

# =========================
# SETUP COMMANDS
# =========================

@bot.tree.command(name="setupstorage", description="Create the storage panel here")
async def setupstorage(interaction: discord.Interaction):

    await interaction.response.defer(ephemeral=True)

    msg = await interaction.channel.send(embed=build_storage_embed())

    config["storage_channel_id"] = interaction.channel.id
    config["storage_message_id"] = msg.id
    save_json(CONFIG_FILE, config)

    await interaction.followup.send("Storage system initialized.", ephemeral=True)

@bot.tree.command(name="setlogchannel", description="Set logging channel")
async def setlogchannel(interaction: discord.Interaction):

    config["log_channel_id"] = interaction.channel.id
    save_json(CONFIG_FILE, config)

    await interaction.response.send_message("Log channel set.", ephemeral=True)

@bot.tree.command(name="setinjurychannel", description="Set injury RP channel")
async def setinjurychannel(interaction: discord.Interaction):

    config["injury_channel_id"] = interaction.channel.id
    save_json(CONFIG_FILE, config)

    await interaction.response.send_message("Injury RP channel set.", ephemeral=True)

# =========================
# STORAGE CHANNEL CHECK
# =========================

def storage_channel_only(interaction):
    return interaction.channel.id == config.get("storage_channel_id")

# =========================
# STORAGE COMMANDS
# =========================

@bot.tree.command(name="add", description="Add item to storage")
async def add(interaction: discord.Interaction, amount: int, item: str):

    if not storage_channel_only(interaction):
        return await interaction.response.send_message("Wrong channel.", ephemeral=True)

    item = normalize(item)
    storage[item] = storage.get(item, 0) + amount

    save_json(DATA_FILE, storage)
    await update_storage_embed()
    await log_action("Added", interaction.user, item, amount, storage[item])

    await interaction.response.send_message("Added to storage.", ephemeral=True)

@bot.tree.command(name="remove", description="Remove item from storage")
async def remove(interaction: discord.Interaction, amount: int, item: str):

    if not storage_channel_only(interaction):
        return await interaction.response.send_message("Wrong channel.", ephemeral=True)

    item = normalize(item)

    if item not in storage:
        return await interaction.response.send_message("Item not found.", ephemeral=True)

    storage[item] -= amount

    if storage[item] <= 0:
        del storage[item]
        total = 0
    else:
        total = storage[item]

    save_json(DATA_FILE, storage)
    await update_storage_embed()
    await log_action("Removed", interaction.user, item, amount, total)

    await interaction.response.send_message("Removed from storage.", ephemeral=True)

@bot.tree.command(name="search", description="Search item")
async def search(interaction: discord.Interaction, item: str):

    item = normalize(item)

    if item in storage:
        await interaction.response.send_message(f"{item}: {storage[item]}")
    else:
        await interaction.response.send_message("Item not found.")

@bot.tree.command(name="lowstock", description="Show low stock")
async def lowstock(interaction: discord.Interaction, threshold: int = 50):

    low_items = [f"{i}: {a}" for i, a in storage.items() if a <= threshold]

    if not low_items:
        await interaction.response.send_message("No low stock.")
    else:
        await interaction.response.send_message("\n".join(low_items))

# =========================
# INJURY SYSTEM
# =========================

@bot.tree.command(name="injury", description="Generate RP injury")
async def injury(
    interaction: discord.Interaction,
    caliber: str,
    location: str,
    distance: int,
    armor: str = "t0"
):

    injury_channel = config.get("injury_channel_id")

    if interaction.channel.id != injury_channel:
        return await interaction.response.send_message(
            "Use this command in the injury RP channel.",
            ephemeral=True
        )

    await interaction.response.defer()

    if armor.lower() not in armor_map:
        return await interaction.followup.send("Use armor tiers T0-T6.")

    try:
        prompt = f"""
        Create a realistic DayZ RP medical injury report.

        Caliber: {caliber}
        Location: {location}
        Distance: {distance} meters
        Armor Tier: {armor}

        Must be survivable.
        Include:
        Severity
        Effects
        Treatment
        """

        response = client.responses.create(
            model="gpt-5-mini",
            input=prompt,
            max_output_tokens=200
        )

        result = response.output[0].content[0].text

        embed = discord.Embed(
            title="🩸 Injury Report",
            color=discord.Color.dark_red(),
            timestamp=datetime.utcnow()
        )

        embed.add_field(name="Caliber", value=caliber)
        embed.add_field(name="Location", value=location)
        embed.add_field(name="Distance", value=f"{distance}m")
        embed.add_field(name="Armor", value=f"{armor.upper()} ({armor_map.get(armor.lower())})", inline=False)
        embed.add_field(name="Medical Report", value=result, inline=False)

        embed.set_footer(text=f"Reported by {interaction.user}")

        await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send(f"Error: {e}")

# =========================

bot.run(TOKEN)
