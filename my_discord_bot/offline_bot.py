import os
import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from datetime import timedelta

# === Settings ===
TOKEN = os.getenv("Secret_Key") or "YOUR_DISCORD_BOT_TOKEN_HERE"
GUILD_ID = 1116737021470314597  # Your server ID for guild command sync

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Role hierarchy (highest to lowest)
ROLES_HIERARCHY = [
    "owner",
    "co-owner",
    "head admin",
    "admin",
    "head mod",
    "mod",
    "moderator"
]

# === Utility: Get highest role level index for a member
def get_highest_role_index(member: discord.Member):
    member_roles = [r.name.lower() for r in member.roles]
    indices = [ROLES_HIERARCHY.index(r) for r in member_roles if r in ROLES_HIERARCHY]
    if indices:
        return min(indices)  # Lower index = higher role
    # Treat guild owner as highest
    if member == member.guild.owner:
        return 0
    return len(ROLES_HIERARCHY) + 1  # lowest

# Check if member has at least required role
def has_required_role(member: discord.Member, required_role: str):
    required_index = ROLES_HIERARCHY.index(required_role.lower())
    member_index = get_highest_role_index(member)
    return member_index <= required_index

# === Offline Utility Globals ===
last_record = ""
repeat_enabled = False
repeat_channel_id = None

# === Moderation Commands ===

@bot.tree.command(name="kick", description="Kick a member from the server", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(member="Member to kick", reason="Reason for kicking")
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    if not has_required_role(interaction.user, "mod"):
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return
    try:
        await member.kick(reason=reason)
        await interaction.response.send_message(f"👢 {member} was kicked. Reason: {reason}")
    except discord.Forbidden:
        await interaction.response.send_message("❌ I cannot kick this member.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

@bot.tree.command(name="ban", description="Ban a member from the server", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(member="Member to ban", reason="Reason for banning")
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    if not has_required_role(interaction.user, "admin"):
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return
    try:
        await member.ban(reason=reason)
        await interaction.response.send_message(f"🔨 {member} was banned. Reason: {reason}")
    except discord.Forbidden:
        await interaction.response.send_message("❌ I cannot ban this member.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

@bot.tree.command(name="unban", description="Unban a user", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(user="User to unban")
async def unban(interaction: discord.Interaction, user: discord.User):
    if not has_required_role(interaction.user, "admin"):
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return
    try:
        await interaction.guild.unban(user)
        await interaction.response.send_message(f"♻️ {user} has been unbanned.")
    except discord.NotFound:
        await interaction.response.send_message("❌ User not found in ban list.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

@bot.tree.command(name="mute", description="Timeout a member", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(member="Member to mute", duration="Duration in minutes", reason="Reason for muting")
async def mute(interaction: discord.Interaction, member: discord.Member, duration: int, reason: str = "No reason provided"):
    if not has_required_role(interaction.user, "mod"):
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return
    until = discord.utils.utcnow() + timedelta(minutes=duration)
    try:
        await member.timeout(until, reason=reason)
        await interaction.response.send_message(f"🔇 {member} muted for {duration} minutes. Reason: {reason}")
    except discord.Forbidden:
        await interaction.response.send_message("❌ I cannot timeout this member.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

@bot.tree.command(name="unmute", description="Remove timeout from a member", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(member="Member to unmute")
async def unmute(interaction: discord.Interaction, member: discord.Member):
    if not has_required_role(interaction.user, "mod"):
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return
    try:
        await member.timeout(None)
        await interaction.response.send_message(f"🔊 {member} has been unmuted.")
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

# === Role Management Commands ===

@bot.tree.command(name="promote", description="Promote a member to the next higher role", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(member="Member to promote")
async def promote(interaction: discord.Interaction, member: discord.Member):
    if not has_required_role(interaction.user, "admin"):
        await interaction.response.send_message("❌ You don't have permission.", ephemeral=True)
        return

    member_roles = [r.name.lower() for r in member.roles]
    # Find current role index (lowest/highest priority)
    for i in reversed(range(len(ROLES_HIERARCHY) - 1)):
        if ROLES_HIERARCHY[i + 1] in member_roles:
            new_role = discord.utils.get(interaction.guild.roles, name=ROLES_HIERARCHY[i])
            old_role = discord.utils.get(interaction.guild.roles, name=ROLES_HIERARCHY[i + 1])
            if new_role and old_role:
                await member.remove_roles(old_role)
                await member.add_roles(new_role)
                await interaction.response.send_message(f"⬆️ {member} promoted to {new_role.name}.")
                return
    await interaction.response.send_message("⚠️ This member cannot be promoted further.", ephemeral=True)

@bot.tree.command(name="demote", description="Demote a member to the next lower role", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(member="Member to demote")
async def demote(interaction: discord.Interaction, member: discord.Member):
    if not has_required_role(interaction.user, "admin"):
        await interaction.response.send_message("❌ You don't have permission.", ephemeral=True)
        return

    member_roles = [r.name.lower() for r in member.roles]
    for i in range(len(ROLES_HIERARCHY) - 1):
        if ROLES_HIERARCHY[i] in member_roles:
            new_role = discord.utils.get(interaction.guild.roles, name=ROLES_HIERARCHY[i + 1])
            old_role = discord.utils.get(interaction.guild.roles, name=ROLES_HIERARCHY[i])
            if new_role and old_role:
                await member.remove_roles(old_role)
                await member.add_roles(new_role)
                await interaction.response.send_message(f"⬇️ {member} demoted to {new_role.name}.")
                return
    await interaction.response.send_message("⚠️ This member cannot be demoted further.", ephemeral=True)

# === Offline Utility Commands ===

@bot.tree.command(name="record", description="Save a record (Mods & above)", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(text="Text to save as record")
async def record_cmd(interaction: discord.Interaction, text: str):
    global last_record
    if not has_required_role(interaction.user, "mod"):
        await interaction.response.send_message("❌ You don't have permission.", ephemeral=True)
        return
    last_record = text
    await interaction.response.send_message(f"✅ Record saved: {text}")

@bot.tree.command(name="print", description="Print the last record (Mods & above)", guild=discord.Object(id=GUILD_ID))
async def print_cmd(interaction: discord.Interaction):
    if not has_required_role(interaction.user, "mod"):
        await interaction.response.send_message("❌ You don't have permission.", ephemeral=True)
        return
    await interaction.response.send_message(f"📝 Last record: {last_record or 'No record saved.'}")

@bot.tree.command(name="repeat", description="Toggle repeating the last record in this channel (Mods & above)", guild=discord.Object(id=GUILD_ID))
async def repeat_cmd(interaction: discord.Interaction):
    global repeat_enabled, repeat_channel_id
    if not has_required_role(interaction.user, "mod"):
        await interaction.response.send_message("❌ You don't have permission.", ephemeral=True)
        return
    repeat_enabled = not repeat_enabled
    repeat_channel_id = interaction.channel_id if repeat_enabled else None
    await interaction.response.send_message(f"🔁 Repeat mode {'enabled' if repeat_enabled else 'disabled'} in this channel.")

@bot.tree.command(name="stop", description="Stop repeat mode manually (Mods & above)", guild=discord.Object(id=GUILD_ID))
async def stop_cmd(interaction: discord.Interaction):
    global repeat_enabled, repeat_channel_id
    if not has_required_role(interaction.user, "mod"):
        await interaction.response.send_message("❌ You don't have permission.", ephemeral=True)
        return
    repeat_enabled = False
    repeat_channel_id = None
    await interaction.response.send_message("🛑 Repeat mode manually stopped.")

@bot.tree.command(name="refresh", description="Erase the saved record and stop repeat (Mods & above)", guild=discord.Object(id=GUILD_ID))
async def refresh_cmd(interaction: discord.Interaction):
    global last_record, repeat_enabled, repeat_channel_id
    if not has_required_role(interaction.user, "mod"):
        await interaction.response.send_message("❌ You don't have permission.", ephemeral=True)
        return
    last_record = ""
    repeat_enabled = False
    repeat_channel_id = None
    await interaction.response.send_message("♻️ Record cleared and repeat mode disabled.")

# === Info Commands ===

@bot.tree.command(name="server_rules", description="Show Akane's usage rules for the server", guild=discord.Object(id=GUILD_ID))
async def server_rules_cmd(interaction: discord.Interaction):
    if not has_required_role(interaction.user, "mod"):
        await interaction.response.send_message("❌ You don't have permission to use this.", ephemeral=True)
        return

    embed = discord.Embed(
        title="📜 Akane Bot Rules & Usage",
        description="Akane has two parts: **AI Bot (Always Online)** & **Offline Utility Bot (Mods+ Only When Active)**",
        color=discord.Color.purple()
    )

    embed.add_field(
        name="🤖 AI Bot Commands (Always Available)",
        value=(
            "@Akane <message> — Chat with AI\n"
            "📎 **Attachment** — Upload a video/image for AI review\n"
            "/status — Check status\n"
            "/joke — Random joke\n"
            "/quote — Random quote\n"
            "/about — Learn about Akane"
        ),
        inline=False
    )

    embed.add_field(
        name="💻 Offline Utility Bot Commands (Mods+ Only When Active)",
        value=(
            "/record <text> — Save a record\n"
            "/print — Show last saved record\n"
            "/repeat — Toggle repeat mode in current channel\n"
            "/stop — Stop repeat manually\n"
            "/refresh — Clear record & disable repeat"
        ),
        inline=False
    )

    embed.add_field(
        name="⚠️ Rules",
        value=(
            "1️⃣ Use AI respectfully\n"
            "2️⃣ Follow server rules\n"
            "3️⃣ Only staff use utility commands\n"
            "4️⃣ Offline bot works only when owner's PC is on"
        ),
        inline=False
    )

    embed.set_footer(text="Stay respectful and enjoy chatting with Akane 💜")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="about", description="Learn about Akane", guild=discord.Object(id=GUILD_ID))
async def about_cmd(interaction: discord.Interaction):
    embed = discord.Embed(
        title="✨ About Akane",
        description="Always happy to help you 💖",
        color=discord.Color.purple()
    )
    embed.add_field(
        name="💡 Creator",
        value="Made with love by **Noviac** for this server.",
        inline=False
    )
    embed.add_field(
        name="🌐 Community",
        value="[Join here!](https://discord.gg/HgZP7tMw)",
        inline=False
    )
    embed.add_field(
        name="📩 Contact",
        value="For further questions, please DM **Noviac**.",
        inline=False
    )
    embed.set_footer(text="😊 Have a nice day! 🌸")
    await interaction.response.send_message(embed=embed)

# === Repeat Listener ===
@bot.event
async def on_message(message):
    global repeat_enabled, last_record, repeat_channel_id
    if message.author.bot:
        return
    if repeat_enabled and last_record and message.channel.id == repeat_channel_id:
        await message.channel.send(last_record)
    await bot.process_commands(message)

# === Sync commands on ready ===
@bot.event
async def on_ready():
    print(f"✅ Bot logged in as {bot.user}")
    await bot.tree.sync(guild=discord.Object(id=GUILD_ID))

# === Run bot ===
async def main():
    async with bot:
        await bot.start(TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except RuntimeError:
        loop = asyncio.get_event_loop()
        loop.create_task(main())
        loop.run_forever()
