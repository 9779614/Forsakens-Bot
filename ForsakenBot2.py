import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from datetime import datetime

TOKEN = os.getenv("DISCORD_TOKEN")

DATA_FILE = "storage.json"
CONFIG_FILE = "config.json"

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# -----------------------
# LOAD / SAVE
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
# AMMO NORMALIZATION
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

def normalize(item: str):
    item = item.lower()
    return ammo_map.get(item, item)

# -----------------------
# EMBED BUILDER
# -----------------------

def build_embed():
    embed = discord.Embed(
        title="📦 Forsaken Communal Storage",
        description="Live Inventory",
        color=discord.Color.orange()
    )

    if not storage:
        embed.add_field(name="Items", value="Empty", inline=False)
    else:
        text = ""
        for item, amount in sorted(storage.items()):
            text += f"**{item}** : {amount}\n"

        embed.add_field(name="Items", value=text, inline=False)

    embed.set_footer(text="Updates automatically")

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

    channel_id = config.get("log_channel_id")
    if not channel_id:
        return

    channel = bot.get_channel(channel_id)
    if not channel:
        return

    embed = discord.Embed(
        title="📦 Storage Log",
        color=discord.Color.blue(),
        timestamp=datetime.utcnow()
    )

    embed.add_field(name="Action", value=action, inline=True)
    embed.add_field(name="Item", value=item, inline=True)
    embed.add_field(name="Amount", value=amount, inline=True)
    embed.add_field(name="Total", value=total, inline=False)

    embed.set_footer(text=f"{user} | ID: {user.id}")

    await channel.send(embed=embed)

# -----------------------
# READY
# -----------------------

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Logged in as {bot.user}")

# -----------------------
# SETUP COMMANDS
# -----------------------

@bot.tree.command(name="setupstorage", description="Setup storage panel")
async def setupstorage(interaction: discord.Interaction):

    await interaction.response.defer(ephemeral=True)

    msg = await interaction.channel.send(embed=build_embed())

    config["channel_id"] = interaction.channel.id
    config["message_id"] = msg.id

    save_json(CONFIG_FILE, config)

    await interaction.followup.send("✅ Storage panel created.", ephemeral=True)

@bot.tree.command(name="setlogchannel", description="Set log channel")
async def setlogchannel(interaction: discord.Interaction):

    config["log_channel_id"] = interaction.channel.id
    save_json(CONFIG_FILE, config)

    await interaction.response.send_message("🧾 Log channel set.", ephemeral=True)

# -----------------------
# PERMISSION CHECK
# -----------------------

def is_storage_channel(interaction):
    return interaction.channel.id == config.get("channel_id")

# -----------------------
# ADD
# -----------------------

@bot.tree.command(name="add", description="Add items")
async def add(interaction: discord.Interaction, amount: int, item: str):

    if not is_storage_channel(interaction):
        await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
        return

    item = normalize(item)
    storage[item] = storage.get(item, 0) + amount

    save_json(DATA_FILE, storage)
    await update_embed()

    await log_action("➕ Added", interaction.user, item, amount, storage[item])

    await interaction.response.send_message(f"➕ {amount} {item}", ephemeral=True)

# -----------------------
# REMOVE
# -----------------------

@bot.tree.command(name="remove", description="Remove items")
async def remove(interaction: discord.Interaction, amount: int, item: str):

    if not is_storage_channel(interaction):
        await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
        return

    item = normalize(item)

    if item not in storage:
        await interaction.response.send_message("❌ Item not found.", ephemeral=True)
        return

    storage[item] -= amount

    if storage[item] <= 0:
        del storage[item]
        total = 0
    else:
        total = storage[item]

    save_json(DATA_FILE, storage)
    await update_embed()

    await log_action("➖ Removed", interaction.user, item, amount, total)

    await interaction.response.send_message(f"➖ {amount} {item}", ephemeral=True)

# -----------------------
# SEARCH
# -----------------------

@bot.tree.command(name="search", description="Search item")
async def search(interaction: discord.Interaction, item: str):

    item = normalize(item)

    if item in storage:
        await interaction.response.send_message(f"🔎 {item}: {storage[item]}")
    else:
        await interaction.response.send_message("❌ Not found.")

# -----------------------
# LOW STOCK
# -----------------------

@bot.tree.command(name="lowstock", description="Low stock items")
async def lowstock(interaction: discord.Interaction, threshold: int = 50):

    items = [f"{i}: {a}" for i, a in storage.items() if a <= threshold]

    if not items:
        await interaction.response.send_message("✅ No low stock.")
    else:
        await interaction.response.send_message("⚠ Low Stock:\n" + "\n".join(items))

# -----------------------

bot.run(TOKEN)
