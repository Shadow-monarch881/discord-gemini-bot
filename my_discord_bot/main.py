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
COOLDOWN_IMAGE_URL = "https://cdn.discordapp.com/attachments/1375603204351590463/1539924812732960819/chert.png?ex=6a88163d&is=6a86c4bd&hm=e7e0ba63a36dabae8e54b186271ab3d7b6b1eb4f47e5ca99a557d0a77859390e&"


# Start Flask webserver in background thread
webserver.start()


# === ENV VARIABLES ===
discord_token = os.getenv("Secret_Key")
gemini_api_key = os.getenv("GEMINI_API_KEY")

if not discord_token or not gemini_api_key:
    raise ValueError("❌ Missing API keys!")


# === GEMINI SETUP ===
genai.configure(api_key=gemini_api_key)

model = genai.GenerativeModel("gemini-2.5-flash")


# === DISCORD BOT SETUP ===
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

user_memory = defaultdict(list)
user_timestamps = {}


# === GLOBALS FOR REPEAT SYSTEM ===
repeat_enabled = False
repeat_channel_id = None
last_record = ""


# ============================================================
# ROLE CHECK
# ============================================================

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


# ============================================================
# TALK COOLDOWN
# ============================================================

def can_talk(user_id, role_level):
    now = datetime.now(timezone.utc)

    if user_id == OWNER_ID or role_level in ["owner", "head_admin"]:
        return True

    timestamps = user_timestamps.get(
        user_id,
        {"start": None, "rest_until": None}
    )

    if timestamps["rest_until"] and now < timestamps["rest_until"]:
        return False

    if not timestamps["start"]:
        user_timestamps[user_id] = {
            "start": now,
            "rest_until": None
        }
        return True

    elapsed = now - timestamps["start"]

    if elapsed >= timedelta(minutes=5):
        user_timestamps[user_id] = {
            "start": None,
            "rest_until": now + timedelta(minutes=2)
        }
        return False

    return True


# ============================================================
# DETAIL DETECTION
# ============================================================

def wants_more_detail(user_input: str):
    text = user_input.lower().strip()

    detail_phrases = [
        "explain more",
        "explain this more",
        "explain that more",
        "tell me more",
        "go deeper",
        "elaborate",
        "elaborate more",
        "more detail",
        "more details",
        "more info",
        "more information",
        "get me more info",
        "give me more info",
        "give me more information",
        "in detail",
        "give me details",
        "expand on that",
        "expand this",
        "explain in detail",
        "detailed explanation",
        "longer explanation",
        "break it down",
        "break this down",
        "how do i fix",
        "how can i fix",
        "help me fix",
        "help me with this",
        "what should i do",
        "give me a solution",
        "give me solutions",
    ]

    return any(phrase in text for phrase in detail_phrases)


# ============================================================
# EVENTS
# ============================================================

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


    # ========================================================
    # REPEAT MODE
    # ========================================================

    if (
        repeat_enabled
        and last_record
        and message.channel.id == repeat_channel_id
    ):
        try:
            await send_long_message(message.channel, last_record)
        except discord.HTTPException as e:
            print(f"❌ Failed to send message in repeat: {e}")


    # ========================================================
    # NAME INTRO
    # ========================================================

    if any(
        q in msg_lower
        for q in ["your name", "who are you", "what is your name"]
    ):
        await message.channel.send(
            "Hehe~ I’m **Akane** 💕 Just your bubbly and curious friend ✨"
        )
        return


    # ========================================================
    # WHO MADE YOU
    # ========================================================

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
            "Eee~ that’s easy! 💖 I was made by my bestie "
            "**Noviác** 🫶✨"
        )
        return


    # ========================================================
    # NSFW FILTER
    # ========================================================

    if any(
        word in msg_lower
        for word in ["nsfw", "18+", "porn", "sex"]
    ):
        await message.channel.send(
            "⚠️ Ew~ nope! I’m a classy lady 💅✨ No NSFW here!"
        )
        return


    # ========================================================
    # AI CHAT
    # ========================================================

    if bot.user in message.mentions:

        if not can_talk(user_id, role_level):
            embed = discord.Embed(
                description="💗 *Shhh~ I'm cooking for Noviác right now!*"
            )
            embed.set_image(url=COOLDOWN_IMAGE_URL)
            await message.channel.send(embed=embed)
            return


        user_input = message.content.replace(
            f"<@{bot.user.id}>",
            ""
        ).strip()


        # Keep existing memory system
        history = user_memory[user_id][-6:]

        chat_session = model.start_chat(history=history)


        # ====================================================
        # RESPONSE LENGTH MODE
        # ====================================================

        detailed = wants_more_detail(user_input)


        if detailed:

            response_rules = """
The user wants more information, more detail, help solving a problem,
or a deeper explanation.

Give a fuller and genuinely useful response.

- Explain the important points clearly.
- Break complicated problems into manageable parts.
- Give practical solutions or next steps when appropriate.
- Use bullet points when there are multiple things to cover.
- Prioritize the most important things first.
- You may use multiple paragraphs.
- Do not repeat the same point in different words.
- Do not add meaningless filler just to make the response longer.
"""

            max_tokens = 700

        else:

            response_rules = """
Keep the response conversational and reasonably concise.

For simple casual messages:
- Usually 2-6 sentences.
- Use fewer words when a simple answer is enough.

For messages where the user is describing a problem,
asking for advice, or clearly needs help:
- Do NOT respond with only sympathy.
- Acknowledge the problem briefly.
- Then actually help with useful advice, ideas, solutions,
  or a practical next step.
- You can use a small number of bullet points if useful.
- Give enough information to be helpful without writing an essay.

General rules:
- Aim for roughly 50-120 words when the topic needs it.
- Answer the main point first.
- Match the user's energy.
- You can add a small follow-up thought or question when natural.
- Do not repeat the user's situation unnecessarily.
- Do not repeat the same advice in different words.
- Do not add motivational speeches or filler.
- Do not turn a simple conversation into a huge analysis.

Never respond with ONLY:
"Oh no, sweetie."
"That sounds hard."
"I understand."
"You've got this."

Those can be part of the response, but the response should still
provide something useful when the user is asking for help.
"""

            max_tokens = 250


        # ====================================================
        # PERSONALITY
        # ====================================================

        styled_prompt = f"""
You are Akane, a friendly and warm AI assistant. 💖

Personality:
- You are cute, supportive, playful, and friendly.
- Talk like a close friend, not like a therapist or formal assistant.
- Use emojis naturally, but don't spam them.
- Match the user's energy and message length.
- When explaining technical or serious topics, be clear and useful
  while remaining friendly.
- Avoid overly romantic or parental vibes.
- If asked who created you, say you were made by your friend
  Noviác in a sweet, affectionate way.

{response_rules}

The user's message is:

{user_input}
"""


        # ====================================================
        # GEMINI REQUEST
        # ====================================================

        async with message.channel.typing():

            reply = await query_gemini_chat(
                chat_session,
                styled_prompt,
                max_tokens
            )


        last_record = reply
        repeat_channel_id = message.channel.id


        await send_long_message(
            message.channel,
            reply
        )


        # ====================================================
        # MEMORY
        # ====================================================

        user_memory[user_id].append({
            "role": "user",
            "parts": [user_input]
        })

        user_memory[user_id].append({
            "role": "model",
            "parts": [reply]
        })

        user_memory[user_id] = user_memory[user_id][-6:]


# ============================================================
# GEMINI HELPER
# ============================================================

async def query_gemini_chat(
    chat_session,
    user_input,
    max_tokens
):
    try:

        response = await chat_session.send_message_async(
            user_input,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=max_tokens,
                temperature=0.8
            )
        )

        return response.text.strip()

    except Exception as e:

        print(f"Error: {e}")

        return (
            "Oopsie~ I had a lil’ hiccup trying to respond 💔"
        )


# ============================================================
# DISCORD MESSAGE SENDER
# ============================================================

async def send_long_message(channel, text):

    if len(text) > 2000:

        chunks = [
            text[i:i + 2000]
            for i in range(0, len(text), 2000)
        ]

        for chunk in chunks:
            await channel.send(chunk)

    else:
        await channel.send(text)


# ============================================================
# RUN
# ============================================================

bot.run(discord_token)
