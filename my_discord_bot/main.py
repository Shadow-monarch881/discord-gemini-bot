import os
import discord
import asyncio
import google.generativeai as genai
from discord.ext import commands
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import webserver  # Import the webserver module

# === CONFIG ===
OWNER_ID = 620819429139415040  # Your Discord user ID

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
    if member.id == OWNER_ID:
        return "owner"
    roles = [r.name.lower() for r in member.roles]
    if member == member.guild.owner or "owner" in roles or "co-owner" in roles:
        return "owner"
    elif "head admin" in roles:
        return "head_admin"
    else:
        return "user"

def can_talk(user_id, role_level):
    now = datetime.now(timezone.utc)
    if user_id == OWNER_ID or role_level in ["owner", "head_admin"]:
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
            await send_long_message(message.channel, last_record)
        except discord.HTTPException as e:
            print(f"❌ Failed to send message in repeat: {e}")

    # === Name intro ===
    if any(q in msg_lower for q in ["your name", "who are you", "what is your name"]):
        await message.channel.send("Hehe~ I’m **Akane** 💕 Just your bubbly and curious friend ✨")
        return

    # === Special reply for “who made you” ===
    if any(q in msg_lower for q in ["who made you", "your creator", "developer", "built you"]):
        await message.channel.send("Eee~ that’s easy! 💖 I was made by my bestie **Noviác** 🫶✨")
        return

    # === NSFW keyword filter ===
    if any(word in msg_lower for word in ["nsfw", "18+", "porn", "sex"]):
        await message.channel.send("⚠️ Ew~ nope! I’m a classy lady 💅✨ No NSFW here!")
        return

    # === AI CHAT ===
    if bot.user in message.mentions:
        if not can_talk(user_id, role_level):
            await message.channel.send("⏳ Babe, I need a tiny break~ be back in 2 mins 💖")
            return

        user_input = message.content.replace(f"<@{bot.user.id}>", "").strip()
        history = user_memory[user_id][-6:]
        chat_session = model.start_chat(history=history)

        # Personality instructions
        styled_prompt = (
            "You are Akane, a friendly and warm AI assistant. 💖 "
            "In casual conversations, you act like a cute, supportive friend with playful expressions. 🥰 "
            "When explaining technical or serious topics, keep your tone clear and professional, "
            "but still friendly and approachable. "
            "If asked who created you, say you were made by your friend Noviác in a sweet, affectionate way. "
            "Avoid overly romantic or parental vibes — keep it like close friends. "
            f"User said: {user_input}"
        )

        async with message.channel.typing():
            reply = await query_gemini_chat(chat_session, styled_prompt)

        last_record = reply
        repeat_channel_id = message.channel.id

        await send_long_message(message.channel, reply)

        user_memory[user_id].append({"role": "user", "parts": [user_input]})
        user_memory[user_id].append({"role": "model", "parts": [reply]})
        user_memory[user_id] = user_memory[user_id][-6:]

# === HELPERS ===
async def query_gemini_chat(chat_session, user_input):
    try:
        response = await chat_session.send_message_async(user_input)
        return response.text.strip()
    except Exception as e:
        print(f"Error: {e}")
        return "Oopsie~ I had a lil’ hiccup trying to respond 💔"

async def send_long_message(channel, text):
    if len(text) > 2000:
        chunks = [text[i:i+2000] for i in range(0, len(text), 2000)]
        for chunk in chunks:
            await channel.send(chunk)
    else:
        await channel.send(text)

# === RUN ===
bot.run(discord_token)
