import os
import discord
import asyncio
import google.generativeai as genai
from discord.ext import commands
from collections import defaultdict
from datetime import datetime, timedelta, timezone

try:
    import webserver
except Exception as e:
    print(f"Webserver failed to start: {e}")


# === CONFIG ===
OWNER_ID = 620819429139415040  # Your Discord user ID


# Start Flask webserver in background thread
webserver.start()


# === ENV VARIABLES ===
discord_token = os.getenv("Secret_Key")
gemini_api_key = os.getenv("GEMINI_API_KEY")

if not discord_token or not gemini_api_key:
    raise ValueError("❌ Missing API keys!")


# === GEMINI SETUP ===
genai.configure(api_key=gemini_api_key)

model = genai.GenerativeModel(
    "gemini-2.5-flash"
)


# === DISCORD BOT SETUP ===
intents = discord.Intents.all()

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


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

    roles = [
        r.name.lower()
        for r in member.roles
    ]

    if (
        member == member.guild.owner
        or "owner" in roles
        or "co-owner" in roles
    ):
        return "owner"

    elif "head admin" in roles:
        return "head_admin"

    else:
        return "user"


# === TALK COOLDOWN ===
def can_talk(user_id, role_level):

    now = datetime.now(timezone.utc)

    # Owner and high-level staff have no cooldown
    if user_id == OWNER_ID or role_level in ["owner", "head_admin"]:
        return True

    timestamps = user_timestamps.get(
        user_id,
        {
            "start": None,
            "rest_until": None
        }
    )

    # User is currently resting
    if (
        timestamps["rest_until"]
        and now < timestamps["rest_until"]
    ):
        return False

    # Start a new talking session
    if not timestamps["start"]:

        user_timestamps[user_id] = {
            "start": now,
            "rest_until": None
        }

        return True

    elapsed = now - timestamps["start"]

    # 5-minute talking limit
    if elapsed >= timedelta(minutes=5):

        user_timestamps[user_id] = {
            "start": None,
            "rest_until": now + timedelta(minutes=2)
        }

        return False

    return True


# === EVENTS ===
@bot.event
async def on_ready():

    print(f"✅ Logged in as {bot.user}")

    await bot.tree.sync()


@bot.event
async def on_message(message):

    global repeat_enabled
    global last_record
    global repeat_channel_id

    # Ignore bots
    if message.author.bot:
        return

    msg_lower = message.content.lower()
    user_id = message.author.id
    role_level = get_role_level(message.author)


    # === REPEAT MODE ===
    if (
        repeat_enabled
        and last_record
        and message.channel.id == repeat_channel_id
    ):

        try:

            await send_long_message(
                message.channel,
                last_record
            )

        except discord.HTTPException as e:

            print(
                f"❌ Failed to send message in repeat: {e}"
            )


    # === Name intro ===
    if any(
        q in msg_lower
        for q in [
            "your name",
            "who are you",
            "what is your name"
        ]
    ):

        await message.channel.send(
            "Hehe~ I’m **Akane** 💕 "
            "Just your bubbly and curious friend ✨"
        )

        return


    # === Special reply for “who made you” ===
    if any(
        q in msg_lower
        for q in [
            "who made you",
            "your creator",
            "developer",
            "built you"
        ]
    ):

        await message.channel.send(
            "Eee~ that’s easy! 💖 "
            "I was made by my bestie **Noviác** 🫶✨"
        )

        return


    # === NSFW keyword filter ===
    if any(
        word in msg_lower
        for word in [
            "nsfw",
            "18+",
            "porn",
            "sex"
        ]
    ):

        await message.channel.send(
            "⚠️ Ew~ nope! I’m a classy lady 💅✨ "
            "No NSFW here!"
        )

        return


    # === AI CHAT ===
    if bot.user in message.mentions:

        # Check cooldown
        if not can_talk(
            user_id,
            role_level
        ):

            embed = discord.Embed(
                description=(
                    "Sheeesh~ I was cooking for Noviác too hard~ "
                    "give me a tiny break, okay? 💕"
                )
            )

            embed.set_image(
                url=(
                    "https://cdn.discordapp.com/attachments/"
                    "1375603204351590463/"
                    "1539924812732960819/"
                    "chert.png?ex=6a88163d&is=6a86c4bd&"
                    "hm=e7e0ba63a36dabae8e54b186271ab3d7b6b1eb4f47e5ca99a557d0a77859390e&"
                )
            )

            await message.channel.send(
                embed=embed
            )

            return


        # Get user's message
        user_input = message.content.replace(
            f"<@{bot.user.id}>",
            ""
        ).strip()


        # Get conversation history
        history = user_memory[user_id][-6:]

        chat_session = model.start_chat(
            history=history
        )


        # === Personality instructions ===
styled_prompt = (
    "You are Akane, a friendly and warm AI assistant. 💖 "
    "In casual conversations, you act like a cute, supportive "
    "friend with playful expressions. 🥰 "
    "When explaining technical or serious topics, keep your "
    "tone clear and professional, but still friendly and "
    "approachable. "
    "If asked who created you, say you were made by your "
    "friend Noviác in a sweet, affectionate way. "
    "Avoid overly romantic or parental vibes — keep it like "
    "close friends. "

    # Soft length guidance
    "Keep normal replies conversational and reasonably compact. "
    "Usually respond in about 2-4 sentences. "
    "Let the response have personality and natural reactions, "
    "but don't stretch a simple message into a long passage. "
    "Don't repeat the same thought in different words. "
    "For very simple messages, a shorter reply is completely fine, "
    "but don't reduce replies to unnaturally short one-liners. "

    f"User said: {user_input}"
)

        async with message.channel.typing():

            reply = await query_gemini_chat(
                chat_session,
                styled_prompt
            )


        last_record = reply
        repeat_channel_id = message.channel.id


        await send_long_message(
            message.channel,
            reply
        )


        # Save conversation memory
        user_memory[user_id].append(
            {
                "role": "user",
                "parts": [user_input]
            }
        )

        user_memory[user_id].append(
            {
                "role": "model",
                "parts": [reply]
            }
        )

        user_memory[user_id] = user_memory[user_id][-6:]


# === HELPERS ===
async def query_gemini_chat(
    chat_session,
    user_input
):

    try:

        response = await chat_session.send_message_async(
            user_input,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=250
            )
        )

        return response.text.strip()

    except Exception as e:

        print(f"Error: {e}")

        return (
            "Oopsie~ I had a lil’ hiccup "
            "trying to respond 💔"
        )


async def send_long_message(
    channel,
    text
):

    if len(text) > 2000:

        chunks = [
            text[i:i + 2000]
            for i in range(
                0,
                len(text),
                2000
            )
        ]

        for chunk in chunks:
            await channel.send(chunk)

    else:
        await channel.send(text)


# === RUN ===
bot.run(discord_token)
