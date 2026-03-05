import discord
from discord.ext import commands
import aiosqlite
import json
import os
import random
from datetime import datetime, timezone, timedelta
import asyncio
import traceback

# ──────────────────────────────────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!rps ', intents=intents, help_command=None)

# Paths
AFK_FILE = "afk_data.json"
DB_FILE = "rps_bot.db"

# AFK storage
def load_afk():
    if os.path.exists(AFK_FILE):
        with open(AFK_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_afk(data):
    with open(AFK_FILE, 'w') as f:
        json.dump(data, f, indent=2)

afk_users = load_afk()

# ──────────────────────────────────────────────────────────────────────────
# Database Setup
# ──────────────────────────────────────────────────────────────────────────
async def create_tables(db):
    await db.execute('''CREATE TABLE IF NOT EXISTS mod_logs 
                        (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                         user_id INTEGER, 
                         action TEXT, 
                         reason TEXT, 
                         moderator_id INTEGER, 
                         timestamp TEXT)''')
    await db.execute('''CREATE TABLE IF NOT EXISTS warns 
                        (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                         user_id INTEGER UNIQUE, 
                         count INTEGER DEFAULT 0)''')
    await db.commit()

@bot.event
async def on_ready():
    print(f'🔥 {bot.user} online — Reverse Pixel Studio domination activated!')
    
    if not hasattr(bot, 'db'):
        bot.db = await aiosqlite.connect(DB_FILE)
        print("aiosqlite connection established!")
    
    await create_tables(bot.db)
    
    # Set custom status: Watching Bunkoo + DND
    activity = discord.Activity(
        type=discord.ActivityType.watching,
        name="Bunkoo"
    )
    await bot.change_presence(
        status=discord.Status.dnd,
        activity=activity
    )
    
    print("Status set: Watching Bunkoo | Do Not Disturb")

# ──────────────────────────────────────────────────────────────────────────
# Global Error Handler
# ──────────────────────────────────────────────────────────────────────────
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    embed = discord.Embed(color=0xFF5555, timestamp=datetime.now(timezone.utc))
    embed.set_author(name="Error", icon_url=ctx.author.display_avatar.url)
    
    if isinstance(error, commands.MissingRequiredArgument):
        embed.title = "Missing Argument"
        embed.description = f"`{error.param.name}` required.\nUsage: `{ctx.prefix}{ctx.command} {ctx.command.signature}`"
    elif isinstance(error, commands.BadArgument):
        embed.title = "Bad Input"
        embed.description = str(error)
    elif isinstance(error, commands.MissingPermissions):
        embed.title = "No Permission"
        embed.description = "You don't have permission to use this."
    elif isinstance(error, commands.BotMissingPermissions):
        embed.title = "Bot Lacks Permission"
        embed.description = "I need more permissions to do that!"
    elif isinstance(error, commands.CommandOnCooldown):
        embed.title = "Cooldown"
        embed.description = f"Try again in **{error.retry_after:.1f}s**."
    else:
        embed.title = "Unexpected Error"
        embed.description = "Something broke — check console."
        print(f"Error in {ctx.command}: {error}")
        traceback.print_exc()
    
    await ctx.send(embed=embed, delete_after=12)

# ──────────────────────────────────────────────────────────────────────────
# AFK System
# ──────────────────────────────────────────────────────────────────────────
@bot.command(name="afk", help="Set or remove your AFK status")
async def afk(ctx, *, reason: str = "AFK (pixel grinding)"):
    uid = str(ctx.author.id)
    if uid in afk_users:
        del afk_users[uid]
        save_afk(afk_users)
        embed = discord.Embed(title="Back Online!", description=f"{ctx.author.mention} is no longer AFK.", color=0x55FF55)
    else:
        afk_users[uid] = {"reason": reason, "since": datetime.now(timezone.utc).isoformat()}
        save_afk(afk_users)
        embed = discord.Embed(title="AFK Set", description=f"{ctx.author.mention} is now AFK.\n**Reason:** {reason}", color=0xFFFF55)
        embed.set_footer(text="Mentions will show this message.")
    await ctx.send(embed=embed)

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # AFK handling
    uid = str(message.author.id)
    if uid in afk_users:
        del afk_users[uid]
        save_afk(afk_users)
        await message.channel.send(embed=discord.Embed(description=f"{message.author.mention} is back!", color=0x55FF55), delete_after=8)

    if message.mentions:
        for member in message.mentions:
            muid = str(member.id)
            if muid in afk_users:
                data = afk_users[muid]
                since = datetime.fromisoformat(data["since"])
                ago = str(timedelta(seconds=(datetime.now(timezone.utc) - since).total_seconds())).split('.')[0]
                embed = discord.Embed(title=f"{member.name} is AFK", color=0xFFAA00,
                                      description=f"**Reason:** {data['reason']}\n**AFK for:** {ago}")
                embed.set_thumbnail(url=member.display_avatar.url)
                await message.channel.send(embed=embed)

    # Basic profanity filter (customize the list!)
    bad_words = ["fuck", "shit", "bitch", "nigga", "retard"]
    if any(word in message.content.lower() for word in bad_words):
        await message.delete()
        await message.channel.send(f"{message.author.mention}, keep it clean in RPS!", delete_after=5)

    await bot.process_commands(message)

# ──────────────────────────────────────────────────────────────────────────
# Moderation
# ──────────────────────────────────────────────────────────────────────────
@bot.command(help="Warn a user (logs it)")
@commands.has_permissions(manage_messages=True)
async def warn(ctx, member: discord.Member, *, reason="No reason given"):
    await bot.db.execute(
        "INSERT INTO mod_logs (user_id, action, reason, moderator_id, timestamp) VALUES (?, ?, ?, ?, ?)",
        (member.id, 'warn', reason, ctx.author.id, datetime.now(timezone.utc).isoformat())
    )
    await bot.db.commit()

    embed = discord.Embed(title="⚠️ Warning Issued", color=0xFFFF00,
                          description=f"{member.mention} warned by {ctx.author.mention}\n**Reason:** {reason}")
    await ctx.send(embed=embed)
    try:
        await member.send(f"You were warned in Reverse Pixel Studio: {reason}")
    except:
        pass

@bot.command(help="Delete last N messages in current channel")
@commands.has_permissions(manage_messages=True)
async def purge(ctx, amount: int):
    amount = min(amount, 100)
    await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f"Purged **{amount}** messages.", delete_after=6)

@bot.command(name="purgechannel", help="Purge up to N messages in a channel (max 500)")
@commands.has_permissions(manage_messages=True)
async def purge_channel(ctx, channel: discord.TextChannel = None, limit: int = 100):
    channel = channel or ctx.channel
    limit = min(max(limit, 1), 500)
    try:
        deleted = await channel.purge(limit=limit)
        embed = discord.Embed(
            title="🧹 Channel Purged",
            description=f"Cleared **{len(deleted)}** messages in {channel.mention}.",
            color=0xFFA500
        )
        embed.set_footer(text=f"Requested by {ctx.author} • Reverse Pixel Studio")
        msg = await ctx.send(embed=embed)
        await asyncio.sleep(8)
        await msg.delete()
    except discord.Forbidden:
        await ctx.send("I need Manage Messages permission in that channel!")
    except Exception as e:
        await ctx.send(f"Purge failed: {str(e)}")

@bot.command(help="Kick a member")
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason="No reason"):
    await member.kick(reason=reason)
    embed = discord.Embed(title="👢 Kicked", color=0xFF8800, description=f"{member} kicked.\n**Reason:** {reason}")
    await ctx.send(embed=embed)

@bot.command(help="Ban a member")
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason="No reason"):
    await member.ban(reason=reason)
    embed = discord.Embed(title="⛔ Banned", color=0xFF0000, description=f"{member} banned.\n**Reason:** {reason}")
    await ctx.send(embed=embed)

@bot.command(help="Lock a channel (prevents @everyone from chatting)")
@commands.has_permissions(manage_channels=True)
async def lock(ctx, channel: discord.TextChannel = None):
    channel = channel or ctx.channel
    try:
        await channel.set_permissions(
            ctx.guild.default_role,
            send_messages=False,
            add_reactions=False,
            reason=f"Locked by {ctx.author} ({ctx.author.id})"
        )
        embed = discord.Embed(title="🔒 Channel Locked", description=f"{channel.mention} is now locked.", color=0xFF0000)
        embed.set_footer(text="Reverse Pixel Studio • Use !rps unlock to open")
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("I don't have permission to manage this channel!")
    except Exception as e:
        await ctx.send(f"Failed to lock: {str(e)}")

@bot.command(help="Unlock a channel")
@commands.has_permissions(manage_channels=True)
async def unlock(ctx, channel: discord.TextChannel = None):
    channel = channel or ctx.channel
    try:
        await channel.set_permissions(
            ctx.guild.default_role,
            send_messages=None,
            add_reactions=None,
            reason=f"Unlocked by {ctx.author} ({ctx.author.id})"
        )
        embed = discord.Embed(title="🔓 Channel Unlocked", description=f"{channel.mention} is now open.", color=0x00FF00)
        embed.set_footer(text="Reverse Pixel Studio")
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("I don't have permission to manage this channel!")
    except Exception as e:
        await ctx.send(f"Failed to unlock: {str(e)}")

# ──────────────────────────────────────────────────────────────────────────
# Utilities
# ──────────────────────────────────────────────────────────────────────────
@bot.command(help="Check bot latency")
async def ping(ctx):
    embed = discord.Embed(title="🏓 Pong!", description=f"{round(bot.latency * 1000)}ms", color=0x00FF88)
    await ctx.send(embed=embed)

@bot.command(help="Show server information")
async def serverinfo(ctx):
    embed = discord.Embed(title=f"{ctx.guild.name} Info", color=0x0099FF)
    embed.add_field(name="Members", value=ctx.guild.member_count)
    embed.add_field(name="Created", value=ctx.guild.created_at.strftime("%d %b %Y"))
    embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
    await ctx.send(embed=embed)

@bot.command(help="Create a yes/no poll")
async def poll(ctx, *, question):
    embed = discord.Embed(title="📊 Poll", description=question, color=0x00AAFF)
    msg = await ctx.send(embed=embed)
    await msg.add_reaction("👍")
    await msg.add_reaction("👎")

@bot.command(name="embed", help="Custom embed builder (placeholder)")
async def embed_builder(ctx):
    await ctx.send("**Embed builder coming soon!**\nUse `!rps assetdrop [description]` for quick studio announces.")

# ──────────────────────────────────────────────────────────────────────────
# Studio Features
# ──────────────────────────────────────────────────────────────────────────
@bot.command(name="assetdrop", help="Announce a new asset drop")
@commands.has_permissions(manage_messages=True)
async def asset_drop(ctx, *, description):
    embed = discord.Embed(title="🎨 New Asset Drop!", description=description, color=0xFF69B4)
    embed.set_footer(text="Reverse Pixel Studio • React with thoughts!")
    await ctx.send(embed=embed)

# ──────────────────────────────────────────────────────────────────────────
# Fun Commands
# ──────────────────────────────────────────────────────────────────────────
@bot.command(name="8ball", help="Ask the Magic 8-Ball a question")
async def eightball(ctx, *, question: str = None):
    if not question:
        return await ctx.send(embed=discord.Embed(
            title="🎱 8-Ball",
            description="Ask a yes/no question! e.g. `!rps 8ball Will my game blow up?`",
            color=0x4B0082
        ))

    responses = [
        "It is certain... your pixels will shine! ✨",
        "Without a doubt — Roblox glory awaits.",
        "Yes definitely, keep grinding.",
        "You may rely on it... but fix the aliasing.",
        "As I see it, yes — epic drop incoming.",
        "Most likely... if you add more detail.",
        "Outlook good — studio vibes strong.",
        "Yes — pixel perfect future.",
        "Signs point to yes... check layers.",
        "Reply hazy, try again after coffee.",
        "Ask again later — rendering in progress.",
        "Better not tell you now... spoiler.",
        "Cannot predict now — RNGesus decides.",
        "Concentrate and ask again... focus!",
        "Don't count on it... bad palette.",
        "My reply is no — rethink design.",
        "My sources say no... too much dither.",
        "Outlook not so good — backup file!",
        "Very doubtful — commission help.",
        "For sure — your game will pop off! 🚀"
    ]

    embed = discord.Embed(title="🎱 Magic 8-Ball", color=0x4B0082)
    embed.add_field(name="Question", value=question, inline=False)
    embed.add_field(name="Answer", value=random.choice(responses), inline=False)
    embed.set_footer(text="Reverse Pixel Studio • Ask wisely...")
    await ctx.send(embed=embed)


@bot.command(name="coinflip", help="Flip a coin — heads or tails?")
async def coinflip(ctx):
    result = random.choice(["Heads 🪙", "Tails 🪙"])
    embed = discord.Embed(title="Coin Flip", description=f"**{result}**", color=0xFFD700)
    embed.set_footer(text="Reverse Pixel Studio")
    await ctx.send(embed=embed)


@bot.command(name="dice", help="Roll a die [sides] — default is d6")
async def dice(ctx, sides: int = 6):
    if sides < 2:
        sides = 6
    result = random.randint(1, sides)
    embed = discord.Embed(title=f"D{sides} Roll", description=f"You rolled a **{result}** 🎲", color=0x00CED1)
    embed.set_footer(text="Reverse Pixel Studio")
    await ctx.send(embed=embed)


@bot.command(name="rps", help="Play Rock Paper Scissors — !rps rps rock / paper / scissors")
async def rockpaperscissors(ctx, choice: str):
    choice = choice.lower()
    if choice not in ["rock", "paper", "scissors"]:
        return await ctx.send("Please choose **rock**, **paper**, or **scissors**!")

    bot_choice = random.choice(["rock", "paper", "scissors"])
    result = ""

    if choice == bot_choice:
        result = "It's a **tie**! 🤝"
    elif (choice == "rock" and bot_choice == "scissors") or \
         (choice == "paper" and bot_choice == "rock") or \
         (choice == "scissors" and bot_choice == "paper"):
        result = "You **win**! 🎉"
    else:
        result = "I **win**! 😏"

    embed = discord.Embed(title="Rock Paper Scissors", color=0x9370DB)
    embed.add_field(name="You played", value=choice.capitalize(), inline=True)
    embed.add_field(name="I played", value=bot_choice.capitalize(), inline=True)
    embed.add_field(name="Result", value=result, inline=False)
    embed.set_footer(text="Reverse Pixel Studio")
    await ctx.send(embed=embed)


@bot.command(name="choose", help="Bot picks one option for you — !rps choose A B C")
async def choose(ctx, *, options: str):
    choices = [opt.strip() for opt in options.split() if opt.strip()]
    if len(choices) < 2:
        return await ctx.send("Give me at least **two** options to choose from!")

    picked = random.choice(choices)
    embed = discord.Embed(title="Decision Time!", description=f"I choose... **{picked}**!", color=0x32CD32)
    embed.set_footer(text="Reverse Pixel Studio • Trust the pixels")
    await ctx.send(embed=embed)


@bot.command(name="hug", help="Send a virtual hug to someone — !rps hug @user")
async def hug(ctx, member: discord.Member = None):
    if not member or member == ctx.author:
        member = ctx.author
        msg = f"**{ctx.author.mention}** gave **themselves** a big hug! 🤗 Self-love!"
    else:
        msg = f"**{ctx.author.mention}** sent a warm hug to **{member.mention}**! 🤗"

    embed = discord.Embed(description=msg, color=0xFFB6C1)
    embed.set_footer(text="Reverse Pixel Studio • Spread the love")
    await ctx.send(embed=embed)


@bot.command(name="roast", help="Get a light-hearted roast — !rps roast @user (optional)")
async def roast(ctx, member: discord.Member = None):
    target = member if member else ctx.author
    roasts = [
        f"{target.mention}'s pixel art is so low-res even Minecraft feels 4K.",
        f"{target.mention} still uses the default Roblox walk animation in 2026...",
        f"{target.mention}'s color palette looks like it was chosen by a toddler on sugar.",
        f"{target.mention} thinks dithering is just 'fancy noise'.",
        f"{target.mention}'s latest game has more bugs than a retro Game Boy cartridge.",
        f"{target.mention} calls 16×16 sprites 'large assets' 😂",
        f"{target.mention}'s commission prices are higher than Roblox DevEx minimum.",
        f"{target.mention} still can't decide between top-down or side-scroller... after 3 years."
    ]
    roast_text = random.choice(roasts)
    embed = discord.Embed(title="🔥 Roast Session", description=roast_text, color=0xFF4500)
    embed.set_footer(text="All love, Reverse Pixel Studio style")
    await ctx.send(embed=embed)

# ──────────────────────────────────────────────────────────────────────────
# Help Command
# ──────────────────────────────────────────────────────────────────────────
@bot.command(name="help", help="Show this help message or info about a command")
async def help_cmd(ctx, cmd_name: str = None):
    if cmd_name:
        cmd = bot.get_command(cmd_name)
        if not cmd:
            return await ctx.send(embed=discord.Embed(
                title="Not Found", description=f"No command `{cmd_name}`.", color=0xFF5555))
        embed = discord.Embed(title=f"!rps {cmd.name}", description=cmd.help or "No description", color=0x00FF88)
        if cmd.aliases:
            embed.add_field(name="Aliases", value=", ".join(cmd.aliases), inline=False)
        embed.add_field(name="Usage", value=f"`!rps {cmd.name} {cmd.signature}`", inline=False)
        return await ctx.send(embed=embed)

    embed = discord.Embed(title="Reverse Pixel Studio Bot", color=0xFF69B4,
                          description="Commands to manage & vibe in your pixel empire • `!rps help [command]` for details")
    embed.set_thumbnail(url=bot.user.display_avatar.url)

    categories = {
        "Moderation": ["warn", "purge", "purgechannel", "kick", "ban", "lock", "unlock"],
        "Utilities": ["ping", "serverinfo", "poll", "afk", "embed"],
        "Studio": ["assetdrop"],
        "Fun": ["8ball", "coinflip", "dice", "rps", "choose", "hug", "roast"]
    }

    for cat, cmds in categories.items():
        desc = ""
        for c in cmds:
            cmd = bot.get_command(c)
            if cmd and cmd.help:
                desc += f"`{cmd.name}` — {cmd.help}\n"
        if desc:
            embed.add_field(name=f"**{cat}**", value=desc, inline=False)

    embed.set_footer(text="Prefix: !rps   •   Built for Reverse Pixel Studio")
    await ctx.send(embed=embed)

# ──────────────────────────────────────────────────────────────────────────
# Run
# ──────────────────────────────────────────────────────────────────────────
async def main():
    async with bot:
        await bot.start(os.getenv('DISCORD_TOKEN'))

if __name__ == "__main__":
    asyncio.run(main())
