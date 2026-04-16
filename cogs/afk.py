import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone
from utils.helpers import format_duration


class AFK(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        # In-memory cache so on_message doesn't hit the DB on every single message
        # { (guild_id, user_id): (reason, timestamp) }
        self._cache: dict[tuple[int, int], tuple[str, float]] = {}
        self._load_cache()

    def _load_cache(self):
        rows = self.db.fetchall("SELECT user_id, guild_id, reason, timestamp FROM afk")
        for user_id, guild_id, reason, timestamp in rows:
            self._cache[(guild_id, user_id)] = (reason, timestamp)

    # -------------------------------------------------------------------------
    # Command
    # -------------------------------------------------------------------------

    @app_commands.command(name="afk", description="Set yourself as AFK with an optional reason.")
    @app_commands.describe(reason="Why you're going AFK (optional)")
    async def afk(self, interaction: discord.Interaction, reason: str = "AFK"):
        guild_id = interaction.guild.id
        user_id = interaction.user.id
        now = datetime.now(timezone.utc).timestamp()

        # Save to DB and cache
        self.db.execute(
            "INSERT OR REPLACE INTO afk (user_id, guild_id, reason, timestamp) VALUES (?, ?, ?, ?)",
            (user_id, guild_id, reason, now),
        )
        self._cache[(guild_id, user_id)] = (reason, now)

        # Add [AFK] prefix to nickname
        member = interaction.user
        current_nick = member.display_name
        if not current_nick.startswith("[AFK]"):
            new_nick = f"[AFK] {current_nick}"
            # Truncate to 32 chars (Discord nickname limit)
            new_nick = new_nick[:32]
            try:
                await member.edit(nick=new_nick, reason="User went AFK")
            except discord.Forbidden:
                pass  # Can't rename server owner or higher roles

        embed = discord.Embed(
            description=f"💤 You're now AFK — **{reason}**",
            color=discord.Color.greyple(),
        )
        await interaction.response.send_message(embed=embed)

    # -------------------------------------------------------------------------
    # Listeners
    # -------------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return

        guild_id = message.guild.id
        author_id = message.author.id

        # --- Clear AFK if the author is AFK ---
        if (guild_id, author_id) in self._cache:
            reason, timestamp = self._cache.pop((guild_id, author_id))
            self.db.execute(
                "DELETE FROM afk WHERE user_id = ? AND guild_id = ?",
                (author_id, guild_id),
            )

            # Remove [AFK] from nickname
            member = message.author
            current_nick = member.display_name
            if current_nick.startswith("[AFK] "):
                original_nick = current_nick[len("[AFK] "):]
                try:
                    # If original nick matches actual username, reset to None (removes override)
                    if original_nick == member.name:
                        await member.edit(nick=None, reason="User returned from AFK")
                    else:
                        await member.edit(nick=original_nick, reason="User returned from AFK")
                except discord.Forbidden:
                    pass

            elapsed = datetime.now(timezone.utc).timestamp() - timestamp
            duration = format_duration(elapsed)

            embed = discord.Embed(
                description=f"👋 Welcome back {member.mention}! You were AFK for **{duration}**.",
                color=discord.Color.green(),
            )
            try:
                await message.channel.send(embed=embed, delete_after=10)
            except discord.Forbidden:
                pass
            return  # Don't also check mentions in the same message

        # --- Notify if any mentioned user is AFK ---
        if not message.mentions:
            return

        for mentioned in message.mentions:
            if mentioned.bot or mentioned.id == author_id:
                continue
            key = (guild_id, mentioned.id)
            if key not in self._cache:
                continue

            reason, timestamp = self._cache[key]
            elapsed = datetime.now(timezone.utc).timestamp() - timestamp
            duration = format_duration(elapsed)

            embed = discord.Embed(
                description=f"💤 **{mentioned.display_name}** is AFK — *{reason}* (for {duration})",
                color=discord.Color.greyple(),
            )
            try:
                await message.channel.send(embed=embed, delete_after=15)
            except discord.Forbidden:
                pass


async def setup(bot):
    await bot.add_cog(AFK(bot))
