import os
import discord
import asyncio
import google.generativeai as genai
from discord.ext import commands
from collections import defaultdict
import webserver  # Import the webserver module

# Start Flask webserver in background thread
webserver.start()

# ENV VARIABLES
discord_token = os.getenv("Secret_Key")
gemini_api_key = os.getenv("GEMINI_API_KEY")
if not discord_token or not gemini_api_key:
    raise ValueError("❌ Missing API keys!")

# GEMINI SETUP
genai.configure(api_key=gemini_api_key)
model = genai.GenerativeModel('gemini-2.5-flash')

# DISCORD BOT SETUP
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

user_memory = defaultdict(list)
user_timestamps = {}

# === GLOBALS for REPEAT SYSTEM ===
repeat_enabled = False
repeat_channel_id = None
last_record = ""

# === ROLE CHECK ===
def get_role_level(member: discord.Member):
    roles = [r.name.lower() for r in member.roles]
    if member == member.guild.owner or "owner" in roles or "co-owner" in roles:
        return "owner"
    elif "head admin" in roles:
        return "head_admin"
    else:
        return "user"

def can_talk(user_id, role_level):
    now = datetime.utcnow()
    if role_level in ["owner", "head_admin"]:
        return True
    timestamps = user_timestamps.get(user_id, {"start": None, "rest_until": None})

    if timestamps["rest_until"] and now < timestamps["rest_until"]:
        return False

    if not timestamps["start"]:
        user_timestamps[user_id] = {"start": now, "rest_until": None}
        return True

    elapsed = now - timestamps["start"]
    if elapsed >= timedelta(minutes=5):
        user_timestamps[user_id] = {"start": None, "rest_until": now + timedelta(minutes=2)}
        return False

    return True

# === EVENTS ===
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    await bot.tree.sync()

@bot.event
async def on_message(message):
    global repeat_enabled, last_record, repeat_channel_id

    if message.author.bot:
        return

    msg_lower = message.content.lower()
    user_id = message.author.id
    role_level = get_role_level(message.author)

    # === REPEAT MODE ===
    if repeat_enabled and last_record and message.channel.id == repeat_channel_id:
        try:
            reply = last_record[:4000]  # Prevent Discord 4000 char error
            await message.channel.send(reply)
        except discord.HTTPException as e:
            print(f"❌ Failed to send message in repeat: {e}")

    # Developer Info
    if bot.user in message.mentions and any(q in msg_lower for q in ["who made you", "your creator", "developer", "built you"]):
        embed = discord.Embed(
            title="🤖 Akane — AI Assistant",
            description="I was created by **Noviac** for his community.",
            color=discord.Color.purple()
        )
        embed.add_field(name="🌐 Server", value="[Join here](https://discord.gg/HgZP7tMw)", inline=False)
        embed.add_field(name="📩 Contact", value="DM **Noviac** for more info.", inline=False)
        embed.set_footer(text="Proudly serving with ❤️")
        await message.channel.send(embed=embed)
        return

    # NSFW keyword filter
    if any(word in msg_lower for word in ["nsfw", "18+", "porn", "sex"]):
        await message.channel.send("⚠️ NSFW content is not allowed.")
        return

    # AI CHAT
    if bot.user in message.mentions:
        if not can_talk(user_id, role_level):
            await message.channel.send("⏳ I'm taking a short break. I'll be back in 2 minutes!")
            return

        user_input = message.content.replace(f"<@{bot.user.id}>", "").strip()
        history = user_memory[user_id][-6:]
        chat_session = model.start_chat(history=history)
        reply = await query_gemini_chat(chat_session, user_input)

        last_record = reply  # Save last response for repeat
        repeat_channel_id = message.channel.id  # Save channel to repeat only here

        await message.channel.send(reply)

        user_memory[user_id].append({"role": "user", "parts": [user_input]})
        user_memory[user_id].append({"role": "model", "parts": [reply]})
        user_memory[user_id] = user_memory[user_id][-6:]

# === HELPERS ===
async def query_gemini_chat(chat_session, user_input):
    try:
        response = await chat_session.send_message_async(user_input)
        return response.text
    except Exception as e:
        print(f"Error: {e}")
        return "Sorry, I had trouble responding."

# === RUN ===
bot.run(discord_token)
