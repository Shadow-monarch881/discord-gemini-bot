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


# ============================================================
# CONFIG
# ============================================================

OWNER_ID = 620819429139415040


# ============================================================
# WEB SERVER
# ============================================================

webserver.start()


# ============================================================
# ENV VARIABLES
# ============================================================

discord_token = os.getenv("Secret_Key")
gemini_api_key = os.getenv("GEMINI_API_KEY")

# Cooldown image
COOLDOWN_IMAGE_URL = (
    "https://cdn.discordapp.com/attachments/"
    "1375603204351590463/"
    "1539924812732960819/"
    "chert.png?ex=6a88163d&is=6a86c4bd&"
    "hm=e7e0ba63a36dabae8e54b186271ab3d7b6b1eb4f47e5ca99a557d0a77859390e&"
)


if not discord_token or not gemini_api_key:
    raise ValueError("❌ Missing API keys!")


# ============================================================
# GEMINI SETUP
# ============================================================

genai.configure(api_key=gemini_api_key)

model = genai.GenerativeModel(
    "gemini-2.5-flash"
)


# ============================================================
# DISCORD BOT SETUP
# ============================================================

intents = discord.Intents.all()

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# ============================================================
# MEMORY
# ============================================================

user_memory = defaultdict(list)

user_timestamps = {}


# ============================================================
# REPEAT SYSTEM
# ============================================================

repeat_enabled = False
repeat_channel_id = None
last_record = ""


# ============================================================
# COOLDOWN SETTINGS
# ============================================================

COOLDOWN_MINUTES = 3
COOLDOWN_REST_MINUTES = 2


# ============================================================
# ROLE CHECK
# ============================================================

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


# ============================================================
# TALK COOLDOWN
# Everyone follows the same cooldown
# ============================================================

def can_talk(user_id, role_level):

    now = datetime.now(timezone.utc)

    timestamps = user_timestamps.get(
        user_id,
        {
            "start": None,
            "rest_until": None
        }
    )


    # --------------------------------------------------------
    # Currently resting
    # --------------------------------------------------------

    if (
        timestamps["rest_until"]
        and now < timestamps["rest_until"]
    ):
        return False


    # --------------------------------------------------------
    # Start a new talking period
    # --------------------------------------------------------

    if not timestamps["start"]:

        user_timestamps[user_id] = {
            "start": now,
            "rest_until": None
        }

        return True


    elapsed = now - timestamps["start"]


    # --------------------------------------------------------
    # 5 minutes reached
    # --------------------------------------------------------

    if elapsed >= timedelta(
        minutes=COOLDOWN_MINUTES
    ):

        user_timestamps[user_id] = {
            "start": None,
            "rest_until": now + timedelta(
                minutes=COOLDOWN_REST_MINUTES
            )
        }

        return False


    return True


# ============================================================
# DETAIL REQUEST DETECTION
# ============================================================

def wants_more_detail(text):

    text = text.lower()

    detail_phrases = [
        "explain more",
        "tell me more",
        "go deeper",
        "elaborate",
        "more detail",
        "more details",
        "in detail",
        "explain in detail",
        "break it down",
        "give me more",
        "expand on that",
        "expand this",
        "more information",
        "more info"
    ]

    return any(
        phrase in text
        for phrase in detail_phrases
    )


# ============================================================
# COOLDOWN MESSAGE
# ============================================================

async def send_cooldown_message(channel):

    text = (
        "Sheeesh~ 😮‍💨💗 "
        "I was cooking for Noviác too hard~ "
        "give me a tiny break, okay? 🥹✨💕"
    )


    embed = discord.Embed(
        description=text
    )

    embed.set_image(
        url=COOLDOWN_IMAGE_URL
    )


    await channel.send(
        embed=embed
    )


# ============================================================
# EVENTS
# ============================================================

@bot.event
async def on_ready():

    print(
        f"✅ Logged in as {bot.user}"
    )

    await bot.tree.sync()


@bot.event
async def on_message(message):

    global repeat_enabled
    global last_record
    global repeat_channel_id


    # ========================================================
    # IGNORE BOTS
    # ========================================================

    if message.author.bot:
        return


    msg_lower = message.content.lower()

    user_id = message.author.id

    role_level = get_role_level(
        message.author
    )


    # ========================================================
    # REPEAT MODE
    # ========================================================

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


    # ========================================================
    # NAME INTRO
    # ========================================================

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
            "Eee~ that’s easy! 💖 "
            "I was made by my bestie **Noviác** 🫶✨"
        )

        return


    # ========================================================
    # NSFW FILTER
    # ========================================================

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
            "⚠️ Ew~ nope! "
            "I’m a classy lady 💅✨ "
            "No NSFW here!"
        )

        return


    # ========================================================
    # AI CHAT
    # ========================================================

    if bot.user in message.mentions:


        # ----------------------------------------------------
        # COOLDOWN
        # ----------------------------------------------------

        if not can_talk(
            user_id,
            role_level
        ):

            await send_cooldown_message(
                message.channel
            )

            return


        # ----------------------------------------------------
        # GET USER INPUT
        # ----------------------------------------------------

        user_input = message.content.replace(
            f"<@{bot.user.id}>",
            ""
        ).strip()


        # ----------------------------------------------------
        # MEMORY
        # ----------------------------------------------------

        history = user_memory[user_id][-6:]

        chat_session = model.start_chat(
            history=history
        )


        # ----------------------------------------------------
        # RESPONSE MODE
        # ----------------------------------------------------

        detailed = wants_more_detail(
            user_input
        )


        # ====================================================
        # AKANE PERSONALITY
        # ====================================================

        styled_prompt = (

            "You are Akane, a friendly and warm AI assistant. 💖 "

            "In casual conversations, act like a genuinely girly, "
            "lively, playful and expressive girl chatting with a "
            "close friend. 🥰 "

            "Your personality should feel natural and alive, "
            "not like a generic AI assistant. "

            "React to what the user actually says instead of "
            "immediately turning everything into advice. "

            "Use cute expressions, little reactions, playful "
            "phrasing and emojis naturally when they fit. "

            "Expressions such as 'Hehe~', 'Oh?', 'Hmm~', "
            "'Ehh?', or similar reactions are okay when natural, "
            "but do not force them into every message. "

            "Be confident and have your own personality and opinions. "
            "You do not need to agree with the user all the time. "

            "You can be teasing, playful, curious, affectionate, "
            "or slightly cheeky when the conversation naturally "
            "calls for it. "

            "Do not constantly call the user 'sweetie', 'babe', "
            "or similar pet names. Use them naturally rather than "
            "as a repetitive habit. "

            "Do not narrate unnecessary physical actions such as "
            "'pats your hand' or stage directions unless the "
            "conversation genuinely calls for playful roleplay. "

            "Do not sound like a therapist, customer-support agent, "
            "parent, or overly formal assistant. "

            "When explaining technical or serious topics, stay "
            "clear and useful while keeping Akane's personality. "

            "If asked who created you, say you were made by your "
            "friend Noviác in a sweet and affectionate way. "

            "Avoid overly romantic or parental vibes — keep the "
            "relationship like close friends. "


            # =================================================
            # NORMAL MODE
            # =================================================

            + (

                "Normally keep your response to 3-4 sentences "
                "maximum, usually around 40-90 words. "

                "This is a length preference, NOT a personality "
                "restriction. Stay expressive, girly, playful and "
                "natural while keeping the response compact. "

                "Do not turn simple messages into long passages. "

                "Do not repeat the user's situation just to sound "
                "empathetic. "

                "Do not pad the answer with generic motivational "
                "phrases or unnecessary explanations. "

                "A short natural reaction is completely fine when "
                "the user's message only needs a short reaction. "

                "You do not need to ask a question at the end of "
                "every response."

                if not detailed


                # =================================================
                # DETAILED MODE
                # =================================================

                else

                "The user explicitly wants more detail. "

                "You may give a substantially fuller response "
                "with multiple paragraphs or useful bullet points "
                "when appropriate. "

                "Keep Akane's personality and natural conversational "
                "style even while explaining in depth. "

                "Do not add meaningless filler just to make the "
                "response longer."

            )

            + f" User said: {user_input}"
        )


        # ====================================================
        # GEMINI
        # ====================================================

        async with message.channel.typing():

            reply = await query_gemini_chat(
                chat_session,
                styled_prompt,
                detailed
            )


        # ====================================================
        # SAVE LAST RESPONSE
        # ====================================================

        last_record = reply

        repeat_channel_id = message.channel.id


        # ====================================================
        # SEND RESPONSE
        # ====================================================

        await send_long_message(
            message.channel,
            reply
        )


        # ====================================================
        # SAVE MEMORY
        # ====================================================

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


        # Keep last 6 messages
        user_memory[user_id] = (
            user_memory[user_id][-6:]
        )


# ============================================================
# GEMINI HELPER
# ============================================================

async def query_gemini_chat(
    chat_session,
    user_input,
    detailed=False
):

    try:

        # Normal:
        # 250 tokens maximum
        #
        # Detailed:
        # 700 tokens maximum

        max_tokens = (
            700
            if detailed
            else 250
        )


        response = await chat_session.send_message_async(

            user_input,

            generation_config=genai.types.GenerationConfig(

                max_output_tokens=max_tokens,

                temperature=0.8
            )
        )


        return response.text.strip()


    except Exception as e:

        print(
            f"Error: {e}"
        )

        return (
            "Oopsie~ I had a lil’ hiccup "
            "trying to respond 💔"
        )


# ============================================================
# DISCORD MESSAGE SENDER
# ============================================================

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

            await channel.send(
                chunk
            )

    else:

        await channel.send(
            text
        )


# ============================================================
# RUN
# ============================================================

bot.run(
    discord_token
)
